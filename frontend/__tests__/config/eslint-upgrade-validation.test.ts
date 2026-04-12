/**
 * Tests for the ESLint and eslint-config-next upgrade in this PR.
 *
 * PR changes validated:
 * - eslint: ^8.57.0 → ^8.57.1
 * - eslint-config-next: ^14.2.0 → ^15.0.0
 *
 * Lockfile changes validated:
 * - eslint-config-next resolves to 15.0.0 (was 14.2.35)
 * - @next/eslint-plugin-next resolves to 15.0.0 (was 14.2.35)
 * - @next/eslint-plugin-next now depends on fast-glob instead of glob
 * - eslint-plugin-react-hooks resolves to 5.1.0 (was 5.0.0-canary-…)
 * - glob@10.3.10 removed from dependency tree
 * - jackspeak removed (was a transitive dep of glob)
 * - fast-glob@3.3.1 added
 * - merge2@1.4.1 added (transitive dep of fast-glob)
 * - eslint-config-next peerDependencies now accept eslint ^9.0.0
 * - eslint-plugin-react-hooks peerDependencies now accept eslint ^9.0.0
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";

type PackageJson = {
  devDependencies: Record<string, string>;
  dependencies?: Record<string, string>;
  [key: string]: unknown;
};

type LockfilePackage = {
  version?: string;
  dev?: boolean;
  resolved?: string;
  integrity?: string;
  license?: string;
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
  peerDependencies?: Record<string, string>;
  peerDependenciesMeta?: Record<string, { optional?: boolean }>;
  link?: boolean;
  inBundle?: boolean;
  optional?: boolean;
};

type PackageLock = {
  name: string;
  version: string;
  lockfileVersion: number;
  packages: Record<string, LockfilePackage>;
};

describe("ESLint and eslint-config-next Upgrade Validation", () => {
  const projectRoot = join(__dirname, "..", "..", "..");
  const packageJsonPath = join(projectRoot, "package.json");
  const packageLockPath = join(projectRoot, "package-lock.json");
  let packageJson: PackageJson;
  let packageLock: PackageLock;

  beforeAll(() => {
    if (!existsSync(packageJsonPath)) throw new Error("package.json not found");
    if (!existsSync(packageLockPath))
      throw new Error("package-lock.json not found");
    packageJson = JSON.parse(readFileSync(packageJsonPath, "utf-8"));
    packageLock = JSON.parse(readFileSync(packageLockPath, "utf-8"));
  });

  // ─── package.json changes ──────────────────────────────────────────────────

  describe("package.json – eslint version bump (^8.57.0 → ^8.57.1)", () => {
    it("eslint should be present as a devDependency", () => {
      expect(packageJson.devDependencies.eslint).toBeDefined();
    });

    it("eslint range should be ^8.57.1", () => {
      expect(packageJson.devDependencies.eslint).toBe("^8.57.1");
    });

    it("eslint range should use caret (minor/patch updates allowed)", () => {
      expect(packageJson.devDependencies.eslint).toMatch(/^\^/);
    });

    it("eslint major version should stay on 8", () => {
      const range = packageJson.devDependencies.eslint;
      const major = parseInt(range.replace(/^\^/, "").split(".")[0]);
      expect(major).toBe(8);
    });

    it("eslint should not be an older patch (< 8.57.1)", () => {
      const range = packageJson.devDependencies.eslint;
      const [major, minor, patch] = range
        .replace(/^\^/, "")
        .split(".")
        .map(Number);
      // Must be exactly 8.57.1 or higher within this range declaration
      expect(major).toBe(8);
      expect(minor).toBe(57);
      expect(patch).toBeGreaterThanOrEqual(1);
    });
  });

  describe("package.json – eslint-config-next major upgrade (^14 → ^15)", () => {
    it("eslint-config-next should be present as a devDependency", () => {
      expect(packageJson.devDependencies["eslint-config-next"]).toBeDefined();
    });

    it("eslint-config-next range should be ^15.0.0", () => {
      expect(packageJson.devDependencies["eslint-config-next"]).toBe("^15.0.0");
    });

    it("eslint-config-next should no longer be on version 14", () => {
      const range = packageJson.devDependencies["eslint-config-next"];
      const major = parseInt(range.replace(/^\^/, "").split(".")[0]);
      expect(major).not.toBe(14);
    });

    it("eslint-config-next should be on major version 15", () => {
      const range = packageJson.devDependencies["eslint-config-next"];
      const major = parseInt(range.replace(/^\^/, "").split(".")[0]);
      expect(major).toBe(15);
    });

    it("eslint-config-next range should use caret", () => {
      expect(packageJson.devDependencies["eslint-config-next"]).toMatch(/^\^/);
    });
  });

  // ─── Lockfile – resolved versions ─────────────────────────────────────────

  describe("lockfile – eslint resolves to 8.57.1", () => {
    it("eslint should be in the lockfile", () => {
      expect(packageLock.packages["node_modules/eslint"]).toBeDefined();
    });

    it("eslint locked version should be 8.57.1", () => {
      expect(packageLock.packages["node_modules/eslint"]?.version).toBe(
        "8.57.1",
      );
    });

    it("eslint entry should be marked as dev", () => {
      expect(packageLock.packages["node_modules/eslint"]?.dev).toBe(true);
    });

    it("eslint entry should have a SHA-512 integrity hash", () => {
      expect(packageLock.packages["node_modules/eslint"]?.integrity).toMatch(
        /^sha512-/,
      );
    });
  });

  describe("lockfile – eslint-config-next resolves to 15.0.0", () => {
    it("eslint-config-next should be in the lockfile", () => {
      expect(
        packageLock.packages["node_modules/eslint-config-next"],
      ).toBeDefined();
    });

    it("eslint-config-next locked version should be 15.0.0", () => {
      expect(
        packageLock.packages["node_modules/eslint-config-next"]?.version,
      ).toBe("15.0.0");
    });

    it("eslint-config-next should no longer resolve to 14.x", () => {
      const version =
        packageLock.packages["node_modules/eslint-config-next"]?.version ?? "";
      const major = parseInt(version.split(".")[0]);
      expect(major).not.toBe(14);
    });

    it("eslint-config-next peerDependencies should accept eslint ^9.0.0", () => {
      const peers =
        packageLock.packages["node_modules/eslint-config-next"]
          ?.peerDependencies;
      expect(peers?.eslint).toBeDefined();
      expect(peers?.eslint).toContain("^9.0.0");
    });

    it("eslint-config-next peerDependencies should still accept eslint ^8.0.0", () => {
      const peers =
        packageLock.packages["node_modules/eslint-config-next"]
          ?.peerDependencies;
      expect(peers?.eslint).toContain("^8.0.0");
    });

    it("eslint-config-next should list @next/eslint-plugin-next as a dependency", () => {
      const deps =
        packageLock.packages["node_modules/eslint-config-next"]?.dependencies;
      expect(deps?.["@next/eslint-plugin-next"]).toBeDefined();
    });

    it("eslint-config-next should list eslint-plugin-react-hooks as a dependency", () => {
      const deps =
        packageLock.packages["node_modules/eslint-config-next"]?.dependencies;
      expect(deps?.["eslint-plugin-react-hooks"]).toBeDefined();
    });
  });

  describe("lockfile – @next/eslint-plugin-next resolves to 15.0.0", () => {
    it("@next/eslint-plugin-next should be in the lockfile", () => {
      expect(
        packageLock.packages["node_modules/@next/eslint-plugin-next"],
      ).toBeDefined();
    });

    it("@next/eslint-plugin-next locked version should be 15.0.0", () => {
      expect(
        packageLock.packages["node_modules/@next/eslint-plugin-next"]?.version,
      ).toBe("15.0.0");
    });

    it("@next/eslint-plugin-next 15.0.0 should depend on fast-glob, not glob", () => {
      const deps =
        packageLock.packages["node_modules/@next/eslint-plugin-next"]
          ?.dependencies;
      expect(deps?.["fast-glob"]).toBeDefined();
      expect(deps?.["glob"]).toBeUndefined();
    });
  });

  describe("lockfile – eslint-plugin-react-hooks stable release (5.1.0)", () => {
    it("eslint-plugin-react-hooks should be in the lockfile", () => {
      expect(
        packageLock.packages["node_modules/eslint-plugin-react-hooks"],
      ).toBeDefined();
    });

    it("eslint-plugin-react-hooks should resolve to 5.1.0", () => {
      expect(
        packageLock.packages["node_modules/eslint-plugin-react-hooks"]?.version,
      ).toBe("5.1.0");
    });

    it("eslint-plugin-react-hooks should no longer be on a canary version", () => {
      const version =
        packageLock.packages["node_modules/eslint-plugin-react-hooks"]
          ?.version ?? "";
      expect(version).not.toContain("canary");
      expect(version).not.toContain("-");
    });

    it("eslint-plugin-react-hooks peerDependencies should accept eslint ^9.0.0", () => {
      const peers =
        packageLock.packages["node_modules/eslint-plugin-react-hooks"]
          ?.peerDependencies;
      expect(peers?.eslint).toBeDefined();
      expect(peers?.eslint).toContain("^9.0.0");
    });
  });

  // ─── Lockfile – removed packages ──────────────────────────────────────────

  describe("lockfile – glob replaced (fast-glob for @next/eslint-plugin-next, non-deprecated glob for jest)", () => {
    it("if glob is present at the top level, it must not be the deprecated glob@10.x", () => {
      const globEntry = packageLock.packages["node_modules/glob"];
      if (globEntry) {
        const major = parseInt((globEntry.version ?? "0").split(".")[0], 10);
        expect(major).not.toBe(10);
        // Should be the non-deprecated version (13+)
        expect(major).toBeGreaterThanOrEqual(13);
      }
    });

    it("@next/eslint-plugin-next should not indirectly require glob", () => {
      const nextPluginDeps =
        packageLock.packages["node_modules/@next/eslint-plugin-next"]
          ?.dependencies ?? {};
      expect(Object.keys(nextPluginDeps)).not.toContain("glob");
    });
  });

  describe("lockfile – jackspeak removed (was transitive dep of glob)", () => {
    it("jackspeak should not be present in the lockfile", () => {
      expect(packageLock.packages["node_modules/jackspeak"]).toBeUndefined();
    });
  });

  // ─── Lockfile – added packages ─────────────────────────────────────────────

  describe("lockfile – fast-glob added (replaces glob)", () => {
    it("fast-glob should be present in the lockfile", () => {
      expect(packageLock.packages["node_modules/fast-glob"]).toBeDefined();
    });

    it("fast-glob locked version should be 3.3.1", () => {
      expect(packageLock.packages["node_modules/fast-glob"]?.version).toBe(
        "3.3.1",
      );
    });

    it("fast-glob should be marked as a dev dependency", () => {
      expect(packageLock.packages["node_modules/fast-glob"]?.dev).toBe(true);
    });

    it("fast-glob should have a SHA-512 integrity hash", () => {
      expect(packageLock.packages["node_modules/fast-glob"]?.integrity).toMatch(
        /^sha512-/,
      );
    });

    it("fast-glob should list merge2 as a direct dependency", () => {
      const deps = packageLock.packages["node_modules/fast-glob"]?.dependencies;
      expect(deps?.["merge2"]).toBeDefined();
    });

    it("fast-glob should list micromatch as a direct dependency", () => {
      const deps = packageLock.packages["node_modules/fast-glob"]?.dependencies;
      expect(deps?.["micromatch"]).toBeDefined();
    });
  });

  describe("lockfile – merge2 added (transitive dep of fast-glob)", () => {
    it("merge2 should be present in the lockfile", () => {
      expect(packageLock.packages["node_modules/merge2"]).toBeDefined();
    });

    it("merge2 locked version should be 1.4.1", () => {
      expect(packageLock.packages["node_modules/merge2"]?.version).toBe(
        "1.4.1",
      );
    });

    it("merge2 should be marked as a dev dependency", () => {
      expect(packageLock.packages["node_modules/merge2"]?.dev).toBe(true);
    });
  });

  // ─── Lockfile – updated plugin versions ───────────────────────────────────

  describe("lockfile – updated eslint plugin versions", () => {
    it("@rushstack/eslint-patch should be present and at least 1.10.3", () => {
      const entry =
        packageLock.packages["node_modules/@rushstack/eslint-patch"];
      expect(entry).toBeDefined();
      const [major, minor, patch] = (entry?.version ?? "0.0.0")
        .split(".")
        .map(Number);
      expect(
        major > 1 ||
          (major === 1 && minor > 10) ||
          (major === 1 && minor === 10 && patch >= 3),
      ).toBe(true);
    });

    it("eslint-plugin-import should be present and at least 2.31.0", () => {
      const entry = packageLock.packages["node_modules/eslint-plugin-import"];
      expect(entry).toBeDefined();
      const [major, minor] = (entry?.version ?? "0.0.0").split(".").map(Number);
      expect(major > 2 || (major === 2 && minor >= 31)).toBe(true);
    });

    it("eslint-plugin-jsx-a11y should be present and at least 6.10.0", () => {
      const entry = packageLock.packages["node_modules/eslint-plugin-jsx-a11y"];
      expect(entry).toBeDefined();
      const [major, minor] = (entry?.version ?? "0.0.0").split(".").map(Number);
      expect(major > 6 || (major === 6 && minor >= 10)).toBe(true);
    });

    it("eslint-plugin-react should be present and at least 7.35.0", () => {
      const entry = packageLock.packages["node_modules/eslint-plugin-react"];
      expect(entry).toBeDefined();
      const [major, minor] = (entry?.version ?? "0.0.0").split(".").map(Number);
      expect(major > 7 || (major === 7 && minor >= 35)).toBe(true);
    });
  });

  // ─── Integration: package.json ↔ lockfile consistency ─────────────────────

  describe("integration – package.json and lockfile in sync for changed deps", () => {
    it("eslint range in package.json should be satisfied by locked version", () => {
      const range = packageJson.devDependencies.eslint; // e.g. "^8.57.1"
      const locked = packageLock.packages["node_modules/eslint"]?.version ?? "";
      const [rangeMajor, rangeMinor, rangePatch] = range
        .replace(/^\^/, "")
        .split(".")
        .map(Number);
      const [lockMajor, lockMinor, lockPatch] = locked.split(".").map(Number);

      expect(lockMajor).toBe(rangeMajor);
      if (lockMinor === rangeMinor) {
        expect(lockPatch).toBeGreaterThanOrEqual(rangePatch);
      } else {
        expect(lockMinor).toBeGreaterThan(rangeMinor);
      }
    });

    it("eslint-config-next range in package.json should be satisfied by locked version", () => {
      const range = packageJson.devDependencies["eslint-config-next"]; // "^15.0.0"
      const locked =
        packageLock.packages["node_modules/eslint-config-next"]?.version ?? "";
      const rangeMajor = parseInt(range.replace(/^\^/, "").split(".")[0]);
      const lockMajor = parseInt(locked.split(".")[0]);

      expect(lockMajor).toBe(rangeMajor);
    });

    it("eslint-config-next root entry should list eslint-plugin-react-hooks", () => {
      const lockedDeps =
        packageLock.packages["node_modules/eslint-config-next"]?.dependencies;
      expect(lockedDeps?.["eslint-plugin-react-hooks"]).toBeDefined();
    });
  });

  // ─── Regression: old versions must not appear ─────────────────────────────

  describe("regression – old versions must not appear in lockfile", () => {
    it("eslint-config-next 14.x must not be present in the lockfile", () => {
      const version =
        packageLock.packages["node_modules/eslint-config-next"]?.version ?? "";
      const major = parseInt(version.split(".")[0]);
      expect(major).toBeGreaterThanOrEqual(15);
    });

    it("@next/eslint-plugin-next 14.x must not be present in the lockfile", () => {
      const version =
        packageLock.packages["node_modules/@next/eslint-plugin-next"]
          ?.version ?? "";
      const major = parseInt(version.split(".")[0]);
      expect(major).toBeGreaterThanOrEqual(15);
    });

    it("eslint-plugin-react-hooks canary version must not be present", () => {
      const version =
        packageLock.packages["node_modules/eslint-plugin-react-hooks"]
          ?.version ?? "";
      expect(version).not.toMatch(/canary/);
    });

    it("eslint 8.57.0 must not be the pinned version (must be at least 8.57.1)", () => {
      const version =
        packageLock.packages["node_modules/eslint"]?.version ?? "";
      expect(version).not.toBe("8.57.0");
    });

    it("glob should not appear anywhere in the dependency tree", () => {
      const globPaths = Object.keys(packageLock.packages).filter(
        (p) => p === "node_modules/glob" || p.endsWith("/node_modules/glob"),
      );
      expect(globPaths).toHaveLength(0);
    });
    });
  });
});
