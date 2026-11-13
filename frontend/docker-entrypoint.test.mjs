import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { runInNewContext } from "node:vm";

for (const [name, value, expected] of [
  ["default", "", "knowledge"],
  ["deployment instance", "tenant-production", "tenant-production"],
  ["quoted and Unicode instance", 'tenant"\\\n\r\t中文', 'tenant"\\\n\r\t中文'],
]) {
  test(
    `frontend entrypoint injects ${name}`,
    { skip: process.platform === "win32" },
    () => {
      const root = mkdtempSync(join(tmpdir(), "sono-runtime-config-"));
      try {
        for (const dir of ["bin", "html", "nginx/templates", "nginx/conf.d"])
          mkdirSync(join(root, dir), { recursive: true });
        writeFileSync(
          join(root, "nginx/templates/default.conf.template"),
          "server {}",
        );
        // Keep nginx/envsubst outside this test; assert the generated browser config.
        writeFileSync(join(root, "bin/nginx"), "#!/bin/sh\nexit 0\n", {
          mode: 0o755,
        });
        writeFileSync(join(root, "bin/envsubst"), "#!/bin/sh\ncat\n", {
          mode: 0o755,
        });
        const script = readFileSync(
          new URL("./docker-entrypoint.sh", import.meta.url),
          "utf8",
        )
          .replaceAll("/usr/share/nginx/html", join(root, "html"))
          .replaceAll("/etc/nginx", join(root, "nginx"));
        writeFileSync(join(root, "entrypoint.sh"), script);
        execFileSync("/bin/sh", [join(root, "entrypoint.sh")], {
          env: {
            ...process.env,
            PATH: `${join(root, "bin")}:${process.env.PATH}`,
            SUMFEN_INSTANCE_ID: value,
            MAX_FILE_SIZE_MB: "50",
            MAX_SKILL_BUNDLE_SIZE_MB: "256",
            DEFAULT_LOCALE: "zh-CN",
          },
        });
        const window = {};
        runInNewContext(readFileSync(join(root, "html/config.js"), "utf8"), {
          window,
        });
        assert.equal(window.__RUNTIME_CONFIG__.SUMFEN_INSTANCE_ID, expected);
        assert.equal(window.__RUNTIME_CONFIG__.MAX_FILE_SIZE_MB, 50);
        assert.equal(window.__RUNTIME_CONFIG__.DEFAULT_LOCALE, "zh-CN");
      } finally {
        rmSync(root, { recursive: true, force: true });
      }
    },
  );
}
