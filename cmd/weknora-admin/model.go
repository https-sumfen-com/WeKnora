package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"strings"
	"text/tabwriter"
	"time"

	"github.com/Tencent/WeKnora/internal/application/repository"
	"github.com/Tencent/WeKnora/internal/types"
	"gorm.io/gorm"
)

// providerPreset provides sensible defaults for known model providers so the
// CLI can accept just `--provider <name>` instead of requiring the full
// base_url + key lookup for every invocation.
type providerPreset struct {
	baseURL   string
	apiKeyEnv string
	// source is the ModelSource enum written to the models.source column.
	// BUILTIN_MODELS.md convention is "remote" for everything cloud-based;
	// parameters.provider inside the JSON carries the actual provider name.
	source string
}

var providerPresets = map[string]providerPreset{
	"aliyun": {
		baseURL:   "https://dashscope.aliyuncs.com/compatible-mode/v1",
		apiKeyEnv: "WEKNORA_ALIYUN_API_KEY",
		source:    string(types.ModelSourceAliyun),
	},
}

// runModel dispatches the `model` subcommand.
func runModel(sub string, args []string) {
	switch sub {
	case "add-builtin":
		err := modelAddBuiltin(args)
		checkExit(err)
	case "list":
		err := modelList(args)
		checkExit(err)
	case "unmark-builtin":
		err := modelUnmarkBuiltin(args)
		checkExit(err)
	case "delete":
		err := modelDelete(args)
		checkExit(err)
	default:
		fmt.Fprintf(os.Stderr, "unknown model subcommand: %s\n", sub)
		fmt.Fprintln(os.Stderr, modelUsage())
		os.Exit(2)
	}
}

func checkExit(err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}

func modelUsage() string {
	return `Model subcommands:
  model add-builtin --type <T> --name <N> --provider <P> [flags]
  model list [--all]
  model unmark-builtin --id <id>
  model delete --id <id>

Flags for add-builtin:
  --type      Embedding | Rerank | KnowledgeQA | VLLM | ASR (required)
  --name      model name e.g. qwen3.6-plus (required)
  --provider  provider preset key e.g. aliyun (required)
  --base-url  overrides provider preset
  --api-key   overrides env (WEKNORA_<PROVIDER>_API_KEY for preset)
  --id        custom ID; defaults to builtin-<type>-<6hex>
  --tenant-id default 10000
  --description  default "Builtin <type> model (<provider>)"
  --is-default   mark as the default for its tenant
  --dimension    Embedding only
  --truncate-prompt-tokens  Embedding only
  --supports-vision  VLLM / KnowledgeQA only`
}

// parseType validates --type against ModelType enum.
func parseType(s string) (types.ModelType, error) {
	switch strings.ToLower(s) {
	case "embedding":
		return types.ModelTypeEmbedding, nil
	case "rerank":
		return types.ModelTypeRerank, nil
	case "knowledgeqa", "llm", "chat":
		return types.ModelTypeKnowledgeQA, nil
	case "vllm":
		return types.ModelTypeVLLM, nil
	case "asr":
		return types.ModelTypeASR, nil
	}
	return "", fmt.Errorf("invalid --type %q (expected Embedding|Rerank|KnowledgeQA|VLLM|ASR)", s)
}

func newBuiltinID(modelType types.ModelType) string {
	b := make([]byte, 3)
	_, _ = rand.Read(b)
	return fmt.Sprintf("builtin-%s-%s", strings.ToLower(string(modelType)), hex.EncodeToString(b))
}

func modelAddBuiltin(args []string) error {
	fs := flag.NewFlagSet("model add-builtin", flag.ContinueOnError)
	typeStr := fs.String("type", "", "model type (required)")
	name := fs.String("name", "", "model name (required)")
	provider := fs.String("provider", "", "provider preset key, e.g. aliyun (required)")
	baseURL := fs.String("base-url", "", "override preset base URL")
	apiKey := fs.String("api-key", "", "override env API key")
	customID := fs.String("id", "", "custom model ID (default: builtin-<type>-<6hex>)")
	tenantID := fs.Uint64("tenant-id", 10000, "owning tenant ID")
	description := fs.String("description", "", "description text")
	isDefault := fs.Bool("is-default", false, "mark as default for its tenant")
	interfaceType := fs.String("interface-type", "", "optional interface type (e.g. openai_compat)")
	dimension := fs.Int("dimension", 0, "Embedding dimension (Embedding type only)")
	truncate := fs.Int("truncate-prompt-tokens", 0, "Embedding truncate prompt tokens (Embedding only)")
	supportsVision := fs.Bool("supports-vision", false, "model accepts images (VLLM / KnowledgeQA)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *typeStr == "" || *name == "" || *provider == "" {
		return fmt.Errorf("--type, --name and --provider are required\n\n%s", modelUsage())
	}

	mType, err := parseType(*typeStr)
	if err != nil {
		return err
	}

	// Resolve provider preset
	preset, hasPreset := providerPresets[strings.ToLower(*provider)]
	effectiveBaseURL := *baseURL
	if effectiveBaseURL == "" {
		if !hasPreset {
			return fmt.Errorf("--base-url required for unknown provider %q", *provider)
		}
		effectiveBaseURL = preset.baseURL
	}
	effectiveKey := *apiKey
	if effectiveKey == "" {
		if hasPreset {
			effectiveKey = os.Getenv(preset.apiKeyEnv)
			if effectiveKey == "" {
				return fmt.Errorf("--api-key not given and env %s is empty", preset.apiKeyEnv)
			}
		} else {
			return fmt.Errorf("--api-key required for unknown provider %q", *provider)
		}
	}
	source := string(types.ModelSourceRemote)
	if hasPreset && preset.source != "" {
		source = preset.source
	}

	id := *customID
	if id == "" {
		id = newBuiltinID(mType)
	}
	desc := *description
	if desc == "" {
		desc = fmt.Sprintf("Builtin %s model (%s)", mType, strings.ToLower(*provider))
	}

	params := types.ModelParameters{
		BaseURL:        effectiveBaseURL,
		APIKey:         effectiveKey,
		InterfaceType:  *interfaceType,
		Provider:       strings.ToLower(*provider),
		SupportsVision: *supportsVision,
	}
	if mType == types.ModelTypeEmbedding {
		dim := *dimension
		if dim == 0 {
			dim = 1024 // sensible default; caller can override
		}
		params.EmbeddingParameters = types.EmbeddingParameters{
			Dimension:            dim,
			TruncatePromptTokens: *truncate,
		}
	}

	model := &types.Model{
		ID:          id,
		TenantID:    *tenantID,
		Name:        *name,
		Type:        mType,
		Source:      types.ModelSource(source),
		Description: desc,
		Parameters:  params,
		IsDefault:   *isDefault,
		IsBuiltin:   true,
		Status:      types.ModelStatusActive,
		CreatedAt:   time.Now(),
		UpdatedAt:   time.Now(),
	}

	db, err := newDB()
	if err != nil {
		return fmt.Errorf("db connect failed: %w", err)
	}
	repo := repository.NewModelRepository(db)

	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()

	// Check if a model with this ID already exists (search across builtin models).
	// GetByID requires tenantID but builtin models match regardless of tenant.
	if existing, _ := repo.GetByID(ctx, *tenantID, id); existing != nil {
		return fmt.Errorf("model id=%s already exists; choose another --id or use 'model delete' first", id)
	}

	// Use SkipHooks so the BeforeCreate hook does not overwrite our chosen ID.
	rawDB := db.Session(&gorm.Session{SkipHooks: true})
	if err := rawDB.Create(model).Error; err != nil {
		return fmt.Errorf("create failed: %w", err)
	}

	fmt.Printf("Builtin model created:\n")
	fmt.Printf("  id          %s\n", model.ID)
	fmt.Printf("  tenant_id   %d\n", model.TenantID)
	fmt.Printf("  type        %s\n", model.Type)
	fmt.Printf("  name        %s\n", model.Name)
	fmt.Printf("  provider    %s\n", params.Provider)
	fmt.Printf("  base_url    %s\n", redactURL(params.BaseURL))
	fmt.Printf("  is_default  %v\n", model.IsDefault)
	fmt.Printf("  is_builtin  true\n")
	return nil
}

// redactURL is a no-op for now; base URLs are not secret themselves but this
// reserves the hook for future preset-level URL rewriting.
func redactURL(u string) string { return u }

func modelList(args []string) error {
	fs := flag.NewFlagSet("model list", flag.ContinueOnError)
	all := fs.Bool("all", false, "list all models, not just builtin")
	if err := fs.Parse(args); err != nil {
		return err
	}

	db, err := newDB()
	if err != nil {
		return err
	}
	var models []types.Model
	q := db.Model(&types.Model{})
	if !*all {
		q = q.Where("is_builtin = ?", true)
	}
	if err := q.Order("type, created_at").Find(&models).Error; err != nil {
		return err
	}

	tw := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
	fmt.Fprintln(tw, "ID\tTYPE\tNAME\tPROVIDER\tIS_BUILTIN\tIS_DEFAULT\tSTATUS")
	for _, m := range models {
		fmt.Fprintf(tw, "%s\t%s\t%s\t%s\t%v\t%v\t%s\n",
			m.ID, m.Type, m.Name, m.Parameters.Provider, m.IsBuiltin, m.IsDefault, m.Status)
	}
	return tw.Flush()
}

func modelUnmarkBuiltin(args []string) error {
	fs := flag.NewFlagSet("model unmark-builtin", flag.ContinueOnError)
	id := fs.String("id", "", "model ID (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *id == "" {
		return fmt.Errorf("--id is required")
	}
	db, err := newDB()
	if err != nil {
		return err
	}
	res := db.Model(&types.Model{}).Where("id = ?", *id).Update("is_builtin", false)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("model id=%s not found", *id)
	}
	fmt.Printf("Model %s: is_builtin=false (now a regular model, editable/deletable)\n", *id)
	return nil
}

func modelDelete(args []string) error {
	fs := flag.NewFlagSet("model delete", flag.ContinueOnError)
	id := fs.String("id", "", "model ID (required)")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *id == "" {
		return fmt.Errorf("--id is required")
	}
	db, err := newDB()
	if err != nil {
		return err
	}
	res := db.Where("id = ?", *id).Delete(&types.Model{})
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return fmt.Errorf("model id=%s not found", *id)
	}
	fmt.Printf("Model %s soft-deleted\n", *id)
	return nil
}
