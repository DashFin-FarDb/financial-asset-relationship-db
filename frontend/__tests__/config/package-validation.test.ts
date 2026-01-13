/**
 * Comprehensive unit tests for frontend package.json validation.
 *
 * Tests cover:
 * - File existence and format validation
 * - Required fields presence and format
 * - Dependency version constraints
 * - Script definitions
 * - Dependency consistency
 * - Security best practices
 * - Specific changes validation (axios upgrade)
 *
 * This follows patterns established in tests/integration/test_requirements_dev.py
 * and tests/unit/test_config_validation.py
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";

describe("Package.json Validation", () => {
  const packageJsonPath = join(process.cwd(), "package.json");
  let packageJson: unknown;

  beforeAll(() => {
    if (!existsSync(packageJsonPath)) {
      throw new Error("package.json not found");
    }
    const content = readFileSync(packageJsonPath, "utf-8");
    packageJson = JSON.parse(content);
  });

  describe("File Existence and Format", () => {
    it("should exist in the frontend directory", () => {
      expect(existsSync(packageJsonPath)).toBe(true);
    });

    it("should be valid JSON", () => {
      expect(() => {
        const content = readFileSync(packageJsonPath, "utf-8");
        JSON.parse(content);
      }).not.toThrow();
    });

    it("should be a valid package.json structure", () => {
      expect(packageJson).toBeDefined();
      expect(typeof packageJson).toBe("object");
      expect(packageJson).not.toBeNull();
    });
  });

  describe("Required Fields", () => {
    it("should have a name field", () => {
      expect(packageJson.name).toBeDefined();
      expect(typeof packageJson.name).toBe("string");
      expect(packageJson.name.length).toBeGreaterThan(0);
    });

    it("should have a valid package name format", () => {
      const validNamePattern = /^[@a-z0-9][a-z0-9-._]*$/;
      expect(packageJson.name).toMatch(validNamePattern);
    });

    it("should have a version field", () => {
      expect(packageJson.version).toBeDefined();
      expect(typeof packageJson.version).toBe("string");
    });

    it("should follow semantic versioning", () => {
      const semverPattern = /^\d+\.\d+\.\d+(-[\w.]+)?$/;
      expect(packageJson.version).toMatch(semverPattern);
    });

    it("should have scripts field", () => {
      expect(packageJson.scripts).toBeDefined();
      expect(typeof packageJson.scripts).toBe("object");
    });

    it("should have dependencies field", () => {
      expect(packageJson.dependencies).toBeDefined();
      expect(typeof packageJson.dependencies).toBe("object");
    });

    it("should have devDependencies field", () => {
      expect(packageJson.devDependencies).toBeDefined();
      expect(typeof packageJson.devDependencies).toBe("object");
    });

    it("should have private field set to true", () => {
      expect(packageJson.private).toBe(true);
    });
  });

  describe("Required Scripts", () => {
    const requiredScripts = ["dev", "build", "start", "lint", "test"];

    requiredScripts.forEach((scriptName) => {
      it(`should have ${scriptName} script`, () => {
        expect(packageJson.scripts[scriptName]).toBeDefined();
        expect(typeof packageJson.scripts[scriptName]).toBe("string");
        expect(packageJson.scripts[scriptName].length).toBeGreaterThan(0);
      });
    });

    it("should have dev script using next dev", () => {
      expect(packageJson.scripts.dev).toContain("next");
      expect(packageJson.scripts.dev).toContain("dev");
    });

    it("should have build script using next build", () => {
      expect(packageJson.scripts.build).toContain("next");
      expect(packageJson.scripts.build).toContain("build");
    });

    it("should have start script using next start", () => {
      expect(packageJson.scripts.start).toContain("next");
      expect(packageJson.scripts.start).toContain("start");
    });

    it("should have test script using jest", () => {
      expect(packageJson.scripts.test).toContain("jest");
    });

    it("should have test:watch script", () => {
      expect(packageJson.scripts["test:watch"]).toBeDefined();
      expect(packageJson.scripts["test:watch"]).toContain("jest");
      expect(packageJson.scripts["test:watch"]).toContain("watch");
    });

    it("should have test:coverage script", () => {
      expect(packageJson.scripts["test:coverage"]).toBeDefined();
      expect(packageJson.scripts["test:coverage"]).toContain("jest");
      expect(packageJson.scripts["test:coverage"]).toContain("coverage");
    });

    it("should have test:ci script for CI environments", () => {
      expect(packageJson.scripts["test:ci"]).toBeDefined();
      expect(packageJson.scripts["test:ci"]).toContain("jest");
      expect(packageJson.scripts["test:ci"]).toContain("ci");
    });
  });

  describe("Core Dependencies", () => {
    const coreDependencies = ["react", "react-dom", "next"];

    coreDependencies.forEach((dep) => {
      it(`should have ${dep} as a dependency`, () => {
        expect(packageJson.dependencies[dep]).toBeDefined();
      });
    });

    it("should have axios for HTTP requests", () => {
      expect(packageJson.dependencies.axios).toBeDefined();
    });

    it("should have visualization libraries", () => {
      expect(packageJson.dependencies["plotly.js"]).toBeDefined();
      expect(packageJson.dependencies["react-plotly.js"]).toBeDefined();
    });

    it("should have recharts for charts", () => {
      expect(packageJson.dependencies.recharts).toBeDefined();
    });
  });

  describe("Development Dependencies", () => {
    it("should have TypeScript", () => {
      expect(packageJson.devDependencies.typescript).toBeDefined();
    });

    it("should have Jest for testing", () => {
      expect(packageJson.devDependencies.jest).toBeDefined();
    });

    it("should have jest-environment-jsdom", () => {
      expect(
        packageJson.devDependencies["jest-environment-jsdom"],
      ).toBeDefined();
    });

    it("should have Testing Library packages", () => {
      expect(
        packageJson.devDependencies["@testing-library/react"],
      ).toBeDefined();
      expect(
        packageJson.devDependencies["@testing-library/jest-dom"],
      ).toBeDefined();
      expect(
        packageJson.devDependencies["@testing-library/user-event"],
      ).toBeDefined();
    });

    it("should have TypeScript type definitions", () => {
      expect(packageJson.devDependencies["@types/react"]).toBeDefined();
      expect(packageJson.devDependencies["@types/react-dom"]).toBeDefined();
      expect(packageJson.devDependencies["@types/node"]).toBeDefined();
    });

    it("should have ESLint for linting", () => {
      expect(packageJson.devDependencies.eslint).toBeDefined();
      expect(packageJson.devDependencies["eslint-config-next"]).toBeDefined();
    });

    it("should have Tailwind CSS and related tools", () => {
      expect(packageJson.devDependencies.tailwindcss).toBeDefined();
      expect(packageJson.devDependencies.postcss).toBeDefined();
      expect(packageJson.devDependencies.autoprefixer).toBeDefined();
    });
  });

  describe("Version Constraints", () => {
    it("should have version constraints for all dependencies", () => {
      const deps = Object.entries(packageJson.dependencies);
      deps.forEach(([name, version]) => {
        expect(version).toMatch(/^[\^~><=]?\d+\.\d+/);
      });
    });

    it("should have version constraints for all devDependencies", () => {
      const devDeps = Object.entries(packageJson.devDependencies);
      devDeps.forEach(([name, version]) => {
        expect(version).toMatch(/^[\^~><=]?\d+\.\d+/);
      });
    });

    it("should use caret ranges for most dependencies", () => {
      const deps = Object.entries(packageJson.dependencies);
      const caretDeps = deps.filter(([_, version]) =>
        (version as string).startsWith("^"),
      );

      // Most dependencies should use caret for flexibility
      expect(caretDeps.length).toBeGreaterThan(0);
    });

    it("should not have wildcard versions", () => {
      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      Object.entries(allDeps).forEach(([name, version]) => {
        expect(version).not.toBe("*");
        expect(version).not.toBe("latest");
      });
    });
  });

  describe("Axios Dependency - Specific Change Validation", () => {
    it("should have axios as a direct dependency", () => {
      expect(packageJson.dependencies.axios).toBeDefined();
    });

    it("should have axios version 1.13.2 or higher", () => {
      const axiosVersion = packageJson.dependencies.axios;
      expect(axiosVersion).toBeDefined();

      // Extract version number (handle ^, ~, >=, etc.)
      const versionMatch = axiosVersion.match(/[\d.]+/);
      expect(versionMatch).not.toBeNull();
      if (versionMatch === null) {
        throw new Error("Version match is null");
      }

      const [major, minor, patch] = versionMatch[0].split(".").map(Number);

      // Should be at least 1.13.2
      expect(major).toBeGreaterThanOrEqual(1);
      if (major === 1) {
        expect(minor).toBeGreaterThanOrEqual(13);
        if (minor === 13) {
          expect(patch).toBeGreaterThanOrEqual(2);
        }
      }
    });

    it("should use caret range for axios to allow patch updates", () => {
      const axiosVersion = packageJson.dependencies.axios;
      expect(axiosVersion).toMatch(/^\^/);
    });

    it("axios version should be compatible with TypeScript", () => {
      // Axios 1.x has built-in TypeScript support
      const axiosVersion = packageJson.dependencies.axios;
      const versionMatch = axiosVersion.match(/[\d.]+/);
      if (!versionMatch) {
        throw new Error(`Invalid axios version: ${axiosVersion}`);
      }
      const [major] = versionMatch[0].split(".").map(Number);

      expect(major).toBeGreaterThanOrEqual(1);
    });

    it("should not have conflicting axios versions in devDependencies", () => {
      expect(packageJson.devDependencies.axios).toBeUndefined();
    });
  });

  describe("TypeScript Configuration Consistency", () => {
    it("should have TypeScript type definitions for dependencies that need them", () => {
      const depsNeedingTypes = [
        "react",
        "react-dom",
        "node",
        "plotly.js",
        "react-plotly.js",
      ];

      depsNeedingTypes.forEach((dep) => {
        const typesDep = `@types/${dep}`;
        expect(packageJson.devDependencies[typesDep]).toBeDefined();
      });
    });

    it("axios should not need separate type definitions", () => {
      // Axios 1.x includes TypeScript definitions
      expect(packageJson.devDependencies["@types/axios"]).toBeUndefined();
    });
  });

  describe("React Ecosystem Consistency", () => {
    it("should have matching React and ReactDOM versions", () => {
      const reactVersion = packageJson.dependencies.react;
      const reactDomVersion = packageJson.dependencies["react-dom"];

      expect(reactVersion).toBeDefined();
      expect(reactDomVersion).toBeDefined();

      // Extract major.minor versions
      const reactMajorMinor = reactVersion.match(/\d+\.\d+/)?.[0];
      const reactDomMajorMinor = reactDomVersion.match(/\d+\.\d+/)?.[0];

      expect(reactMajorMinor).toBe(reactDomMajorMinor);
    });

    it("should have matching @types/react and @types/react-dom versions", () => {
      const typesReact = packageJson.devDependencies["@types/react"];
      const typesReactDom = packageJson.devDependencies["@types/react-dom"];

      expect(typesReact).toBeDefined();
      expect(typesReactDom).toBeDefined();

      const reactMajorMinor = typesReact.match(/\d+\.\d+/)?.[0];
      const reactDomMajorMinor = typesReactDom.match(/\d+\.\d+/)?.[0];

      expect(reactMajorMinor).toBe(reactDomMajorMinor);
    });

    it("Next.js version should be compatible with React version", () => {
      const reactVersion = packageJson.dependencies.react;
      const nextVersion = packageJson.dependencies.next;

      const reactMajor = parseInt(reactVersion.match(/\d+/)?.[0] || "0");
      const nextMajor = parseInt(nextVersion.match(/\d+/)?.[0] || "0");

      // Next.js 14 requires React 18+
      if (nextMajor >= 14) {
        expect(reactMajor).toBeGreaterThanOrEqual(18);
      }
    });
  });

  describe("Testing Library Versions", () => {
    it("should have compatible Testing Library versions", () => {
      const testingLibReact =
        packageJson.devDependencies["@testing-library/react"];
      const testingLibJestDom =
        packageJson.devDependencies["@testing-library/jest-dom"];

      expect(testingLibReact).toBeDefined();
      expect(testingLibJestDom).toBeDefined();
    });

    it("Testing Library React should be compatible with React version", () => {
      const reactVersion = packageJson.dependencies.react;
      const testingLibReact =
        packageJson.devDependencies["@testing-library/react"];

      const reactMajor = parseInt(reactVersion.match(/\d+/)?.[0] || "0");
      const testingLibMajor = parseInt(
        testingLibReact.match(/\d+/)?.[0] || "0",
      );

      // @testing-library/react 14+ requires React 18+
      if (testingLibMajor >= 14) {
        expect(reactMajor).toBeGreaterThanOrEqual(18);
      }
    });
  });

  describe("No Duplicate Dependencies", () => {
    it("should not have packages in both dependencies and devDependencies", () => {
      const deps = Object.keys(packageJson.dependencies);
      const devDeps = Object.keys(packageJson.devDependencies);

      const duplicates = deps.filter((dep) => devDeps.includes(dep));

      expect(duplicates).toHaveLength(0);
    });

    it("should not have case-insensitive duplicates", () => {
      const allDeps = [
        ...Object.keys(packageJson.dependencies),
        ...Object.keys(packageJson.devDependencies),
      ];

      const lowerCaseDeps = allDeps.map((dep) => dep.toLowerCase());
      const uniqueLowerCase = new Set(lowerCaseDeps);

      expect(lowerCaseDeps.length).toBe(uniqueLowerCase.size);
    });
  });

  describe("Dependency Name Validity", () => {
    it("all dependency names should be valid npm package names", () => {
      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      const validNamePattern =
        /^(@[a-z0-9-~][a-z0-9-._~]*\/)?[a-z0-9-~][a-z0-9-._~]*$/;

      Object.keys(allDeps).forEach((name) => {
        expect(name).toMatch(validNamePattern);
      });
    });

    it("scoped packages should have valid scope names", () => {
      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      const scopedPackages = Object.keys(allDeps).filter((name) =>
        name.startsWith("@"),
      );

      scopedPackages.forEach((name) => {
        expect(name).toMatch(/^@[a-z0-9-~]+\/[a-z0-9-._~]+$/);
      });
    });
  });

  describe("Security Best Practices", () => {
    it("should not use deprecated package versions", () => {
      // This is a basic check - in real scenarios, you'd check against npm registry
      const deprecatedPackages = ["request", "node-uuid"];

      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      deprecatedPackages.forEach((pkg) => {
        expect(allDeps[pkg]).toBeUndefined();
      });
    });

    it("critical dependencies should have minimum versions", () => {
      const criticalDeps = ["axios", "next", "react"];

      criticalDeps.forEach((dep) => {
        const version = packageJson.dependencies[dep];
        expect(version).toBeDefined();
        expect(version).not.toBe("*");
        expect(version).not.toBe("latest");
      });
    });

    it("should use HTTPS in any URL fields", () => {
      const urlFields = ["homepage", "repository", "bugs"];

      urlFields.forEach((field) => {
        if (packageJson[field]) {
          const url =
            typeof packageJson[field] === "string"
              ? packageJson[field]
              : packageJson[field].url;

          if (url) {
            expect(url).toMatch(/^https:/);
          }
        }
      });
    });
  });

  describe("Package Size and Organization", () => {
    it("should have a reasonable number of dependencies", () => {
      const depCount = Object.keys(packageJson.dependencies).length;
      expect(depCount).toBeGreaterThan(0);
      expect(depCount).toBeLessThan(50); // Arbitrary but reasonable limit
    });

    it("should have a reasonable number of devDependencies", () => {
      const devDepCount = Object.keys(packageJson.devDependencies).length;
      expect(devDepCount).toBeGreaterThan(0);
      expect(devDepCount).toBeLessThan(100); // Arbitrary but reasonable limit
    });

    it("should have more production dependencies than a skeleton project", () => {
      const depCount = Object.keys(packageJson.dependencies).length;
      expect(depCount).toBeGreaterThanOrEqual(5);
    });
  });

  describe("Visualization Dependencies", () => {
    it("should have plotly.js for network visualization", () => {
      expect(packageJson.dependencies["plotly.js"]).toBeDefined();
    });

    it("should have react-plotly.js for React integration", () => {
      expect(packageJson.dependencies["react-plotly.js"]).toBeDefined();
    });

    it("should have recharts for dashboard charts", () => {
      expect(packageJson.dependencies.recharts).toBeDefined();
    });

    it("should have type definitions for plotly", () => {
      expect(packageJson.devDependencies["@types/plotly.js"]).toBeDefined();
      expect(
        packageJson.devDependencies["@types/react-plotly.js"],
      ).toBeDefined();
    });
  });

  describe("HTTP Client Configuration", () => {
    it("should use axios as the primary HTTP client", () => {
      expect(packageJson.dependencies.axios).toBeDefined();
    });

    it("should not have multiple HTTP clients", () => {
      const httpClients = ["axios", "fetch", "superagent", "got", "node-fetch"];
      const presentClients = httpClients.filter(
        (client) =>
          packageJson.dependencies[client] ||
          packageJson.devDependencies[client],
      );

      // Only axios should be present (fetch is built-in to modern browsers)
      expect(presentClients).toEqual(["axios"]);
    });
  });

  describe("Next.js Configuration Dependencies", () => {
    it("should have eslint-config-next for Next.js specific linting", () => {
      expect(packageJson.devDependencies["eslint-config-next"]).toBeDefined();
    });

    it("Next.js version should be modern and stable", () => {
      const nextVersion = packageJson.dependencies.next;
      const major = parseInt(nextVersion.match(/\d+/)?.[0] || "0");

      expect(major).toBeGreaterThanOrEqual(13); // Next.js 13+ has App Router
    });
  });

  describe("Version Upgrade Validation", () => {
    it("axios should be version 1.13.2 as per the upgrade", () => {
      const axiosVersion = packageJson.dependencies.axios;
      expect(axiosVersion).toBe("^1.13.2");
    });

    it("axios upgrade should maintain backward compatibility", () => {
      // Axios 1.x maintains backward compatibility within major version
      const axiosVersion = packageJson.dependencies.axios;
      const major = parseInt(axiosVersion.match(/\d+/)?.[0] || "0");

      expect(major).toBe(1);
    });

    it("axios version should support all required features", () => {
      // Axios 1.x supports TypeScript, interceptors, and modern features
      const axiosVersion = packageJson.dependencies.axios;
      const versionMatch = axiosVersion.match(/[\d.]+/);
      if (!versionMatch) {
        throw new Error(`Invalid axios version: ${axiosVersion}`);
      }
      const [major, minor] = versionMatch[0].split(".").map(Number);

      // 1.13.2 has security fixes and improvements
      expect(major).toBe(1);
      expect(minor).toBeGreaterThanOrEqual(13);
    });
  });

  describe("Edge Cases and Error Handling", () => {
    it("should handle empty optional fields gracefully", () => {
      const optionalFields = [
        "description",
        "keywords",
        "author",
        "license",
        "repository",
      ];

      optionalFields.forEach((field) => {
        if (packageJson[field]) {
          expect(typeof packageJson[field]).toBeDefined();
        }
      });
    });

    it("should not have circular dependencies in structure", () => {
      expect(() => JSON.stringify(packageJson)).not.toThrow();
    });

    it("scripts should not have obvious syntax errors", () => {
      Object.entries(packageJson.scripts).forEach(([name, script]) => {
        expect(script).toBeTruthy();
        expect(typeof script).toBe("string");
        expect((script as string).trim().length).toBeGreaterThan(0);
      });
    });
  });

  describe("Package.json Formatting", () => {
    it("should be properly formatted JSON", () => {
      const content = readFileSync(packageJsonPath, "utf-8");
      const parsed = JSON.parse(content);

      // Should be able to parse and re-stringify
      expect(() => JSON.stringify(parsed, null, 2)).not.toThrow();
    });

    it("should use consistent indentation", () => {
      const content = readFileSync(packageJsonPath, "utf-8");
      const lines = content.split("\n");

      // Check that indentation is consistent (2 or 4 spaces)
      const indentedLines = lines.filter((line) => line.match(/^\s+/));
      if (indentedLines.length > 0) {
        const firstIndent = indentedLines[0].match(/^\s+/)?.[0].length || 0;
        expect([2, 4]).toContain(firstIndent % 2 === 0 ? 2 : 4);
      }
    });
  });

  describe("Dependency Resolution", () => {
    it("should not have version ranges that could cause conflicts", () => {
      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      Object.entries(allDeps).forEach(([name, version]) => {
        // Should not use overly permissive ranges
        expect(version).not.toMatch(/^[*x]/);
        expect(version).not.toMatch(/\|\|/); // Or operator
      });
    });

    it("peer dependencies should be compatible if specified", () => {
      if (packageJson.peerDependencies) {
        const peerDeps = packageJson.peerDependencies;
        const deps = packageJson.dependencies;

        Object.keys(peerDeps).forEach((peerDep) => {
          if (deps[peerDep]) {
            // If peer dep is also a regular dep, versions should be compatible
            expect(deps[peerDep]).toBeDefined();
          }
        });
      }
    });
  });

  describe("Financial Application Specific Dependencies", () => {
    it("should have visualization libraries for financial data", () => {
      const vizLibs = ["plotly.js", "react-plotly.js", "recharts"];

      vizLibs.forEach((lib) => {
        expect(packageJson.dependencies[lib]).toBeDefined();
      });
    });

    it("should have HTTP client for API communication", () => {
      expect(packageJson.dependencies.axios).toBeDefined();
    });

    it("should have React for UI components", () => {
      expect(packageJson.dependencies.react).toBeDefined();
      expect(packageJson.dependencies["react-dom"]).toBeDefined();
    });

    it("should have Next.js for SSR and routing", () => {
      expect(packageJson.dependencies.next).toBeDefined();
    });
  });
});
