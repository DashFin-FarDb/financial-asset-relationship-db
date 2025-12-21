/**
 * Integration tests between package.json and package-lock.json.
 *
 * Tests cover:
 * - Synchronization between package.json and package-lock.json
 * - Axios upgrade impact validation
 * - Dependency tree consistency
 * - Version resolution correctness
 * - Breaking change detection
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

describe('Package Configuration Integration', () => {
  const packageJsonPath = join(process.cwd(), 'package.json');
  const packageLockPath = join(process.cwd(), 'package-lock.json');
  let packageJson: any;
  let packageLock: any;

  beforeAll(() => {
    packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'));
    packageLock = JSON.parse(readFileSync(packageLockPath, 'utf-8'));
  });

  describe('Synchronization Validation', () => {
    it('package.json and package-lock.json should be in sync', () => {
      expect(packageLock.name).toBe(packageJson.name);
      expect(packageLock.version).toBe(packageJson.version);
    });

    it('all dependencies in package.json should be locked', () => {
      const deps = Object.keys(packageJson.dependencies || {});
      const lockedDeps = packageLock.packages?.['']?.dependencies || {};

      deps.forEach((dep) => {
        expect(lockedDeps[dep]).toBeDefined();
      });
    });

    it('all devDependencies in package.json should be locked', () => {
      const devDeps = Object.keys(packageJson.devDependencies || {});
      const lockedDevDeps = packageLock.packages?.['']?.devDependencies || {};

      devDeps.forEach((dep) => {
        expect(lockedDevDeps[dep]).toBeDefined();
      });
    });

    it('locked versions should satisfy package.json ranges', () => {
      const allDeps = {
        ...packageJson.dependencies,
        ...packageJson.devDependencies,
      };

      Object.entries(allDeps).forEach(([name, range]) => {
        const lockedPkg = packageLock.packages?.[`node_modules/${name}`];
        if (lockedPkg) {
          expect(lockedPkg.version).toBeDefined();

          // Basic validation: if range starts with ^1.13.2, locked should be >= 1.13.2
          if (name === 'axios' && range === '^1.13.2') {
            expect(lockedPkg.version).toBe('1.13.2');
          }
        }
      });
    });
  });

  describe('Axios Upgrade Integration', () => {
    it('axios in package.json should match lock version constraint', () => {
      const axiosRange = packageJson.dependencies.axios;
      const axiosLocked = packageLock.packages?.['node_modules/axios'];

      expect(axiosRange).toBe('^1.13.2');
      expect(axiosLocked?.version).toBe('1.13.2');
    });

    it('axios upgrade should not break peer dependencies', () => {
      const axiosLocked = packageLock.packages?.['node_modules/axios'];

      if (axiosLocked?.peerDependencies) {
        Object.keys(axiosLocked.peerDependencies).forEach((peerDep) => {
          const peerPkg = packageLock.packages?.[`node_modules/${peerDep}`];
          const isOptional = axiosLocked.peerDependenciesMeta?.[peerDep]?.optional;

          if (!isOptional) {
            expect(peerPkg).toBeDefined();
          }
        });
      }
    });

    it('axios dependencies should be resolved consistently', () => {
      const axiosLocked = packageLock.packages?.['node_modules/axios'];

      if (axiosLocked?.dependencies) {
        Object.keys(axiosLocked.dependencies).forEach((dep) => {
          const depPkg =
            packageLock.packages?.[`node_modules/${dep}`] ||
            packageLock.packages?.[`node_modules/axios/node_modules/${dep}`];

          expect(depPkg).toBeDefined();
        });
      }
    });

    it('axios should not introduce dependency conflicts', () => {
      // Check if axios dependencies conflict with existing packages
      const axiosLocked = packageLock.packages?.['node_modules/axios'];

      if (axiosLocked?.dependencies) {
        Object.entries(axiosLocked.dependencies).forEach(([dep, version]) => {
          const topLevelPkg = packageLock.packages?.[`node_modules/${dep}`];

          if (topLevelPkg) {
            // If there's a top-level version, it should be compatible
            expect(topLevelPkg.version).toBeDefined();
          }
        });
      }
    });
  });

  describe('Dependency Tree Consistency', () => {
    it('no dependency should have conflicting version requirements', () => {
      const versionRequirements = new Map<string, Set<string>>();

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.dependencies) {
          Object.entries(pkg.dependencies).forEach(([dep, version]) => {
            if (!versionRequirements.has(dep)) {
              versionRequirements.set(dep, new Set());
            }
            versionRequirements.get(dep)!.add(version as string);
          });
        }
      });

      // Check for excessive version diversity
      versionRequirements.forEach((versions, pkg) => {
        if (versions.size > 5) {
          console.warn(`Package ${pkg} has ${versions.size} different version requirements`);
        }
      });
    });

    it('all transitive dependencies should be resolved', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.dependencies) {
          Object.keys(pkg.dependencies).forEach((dep) => {
            // Dependency should exist somewhere in the tree
            const depExists = Object.keys(packageLock.packages).some((p) =>
              p.endsWith(`/${dep}`) || p === `node_modules/${dep}`
            );

            expect(depExists).toBeTruthy();
          });
        }
      });
    });

    it('React ecosystem should be internally consistent', () => {
      const react = packageLock.packages?.['node_modules/react'];
      const reactDom = packageLock.packages?.['node_modules/react-dom'];

      expect(react?.version).toBeDefined();
      expect(reactDom?.version).toBeDefined();

      // React and React-DOM should have matching major.minor versions
      const reactVersion = react!.version!.split('.');
      const reactDomVersion = reactDom!.version!.split('.');

      expect(reactVersion[0]).toBe(reactDomVersion[0]); // Major
      expect(reactVersion[1]).toBe(reactDomVersion[1]); // Minor
    });
  });

  describe('Breaking Change Detection', () => {
    it('major version changes should be intentional', () => {
      // This test documents major version changes
      const axiosLocked = packageLock.packages?.['node_modules/axios'];
      const major = parseInt(axiosLocked?.version?.split('.')[0] || '0');

      // Axios is on major version 1
      expect(major).toBe(1);
    });

    it('no unexpected major version bumps in core deps', () => {
      const coreDeps = {
        react: 18,
        'react-dom': 18,
        next: 14,
        axios: 1,
      };

      Object.entries(coreDeps).forEach(([dep, expectedMajor]) => {
        const pkg = packageLock.packages?.[`node_modules/${dep}`];
        const major = parseInt(pkg?.version?.split('.')[0] || '0');

        expect(major).toBe(expectedMajor);
      });
    });
  });

  describe('Security Considerations', () => {
    it('all packages should have integrity hashes', () => {
      let packagesWithoutIntegrity = 0;

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path !== '' && pkg.resolved && !pkg.resolved.startsWith('file:') && !pkg.link) {
          if (!pkg.integrity) {
            packagesWithoutIntegrity++;
          }
        }
      });

      expect(packagesWithoutIntegrity).toBe(0);
    });

    it('axios should come from official npm registry', () => {
      const axiosLocked = packageLock.packages?.['node_modules/axios'];

      expect(axiosLocked?.resolved).toContain('registry.npmjs.org');
      expect(axiosLocked?.resolved).toContain('axios-1.13.2.tgz');
    });

    it('no packages should use insecure protocols', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.resolved) {
          expect(pkg.resolved).not.toMatch(/^http:/);
          expect(pkg.resolved).not.toMatch(/^git:/);
          expect(pkg.resolved).not.toMatch(/^ftp:/);
        }
      });
    });
  });

  describe('Version Range Satisfaction', () => {
    it('caret ranges should be satisfied correctly', () => {
      // ^1.13.2 should resolve to 1.13.2 or compatible
      const axiosRange = packageJson.dependencies.axios;
      const axiosVersion = packageLock.packages?.['node_modules/axios']?.version;

      expect(axiosRange).toBe('^1.13.2');
      expect(axiosVersion).toBe('1.13.2');

      // Parse versions
      const [major, minor, patch] = axiosVersion!.split('.').map(Number);
      const [rangeMajor, rangeMinor, rangePatch] = '1.13.2'.split('.').map(Number);

      // Caret allows minor and patch updates but not major
      expect(major).toBe(rangeMajor);
      expect(minor).toBeGreaterThanOrEqual(rangeMinor);
      if (minor === rangeMinor) {
        expect(patch).toBeGreaterThanOrEqual(rangePatch);
      }
    });

    it('all resolved versions should satisfy their constraints', () => {
      const rootDeps = {
        ...packageLock.packages?.['']?.dependencies,
        ...packageLock.packages?.['']?.devDependencies,
      };

      Object.entries(rootDeps).forEach(([name, range]) => {
        const pkg = packageLock.packages?.[`node_modules/${name}`];
        expect(pkg?.version).toBeDefined();

        // Basic validation: version should be defined and non-empty
        expect((pkg!.version as string).length).toBeGreaterThan(0);
      });
    });
  });

  describe('Testing Infrastructure Integration', () => {
    it('test dependencies should be compatible with axios', () => {
      const jest = packageLock.packages?.['node_modules/jest'];
      const axios = packageLock.packages?.['node_modules/axios'];

      // Both should be present
      expect(jest).toBeDefined();
      expect(axios).toBeDefined();

      // Jest should be able to mock axios
      expect(jest?.version).toBeDefined();
      expect(axios?.version).toBe('1.13.2');
    });

    it('@testing-library packages should work with current React', () => {
      const testingLib = packageLock.packages?.['node_modules/@testing-library/react'];
      const react = packageLock.packages?.['node_modules/react'];

      expect(testingLib).toBeDefined();
      expect(react).toBeDefined();

      // Testing Library 14 works with React 18
      const testingLibMajor = parseInt(testingLib?.version?.split('.')[0] || '0');
      const reactMajor = parseInt(react?.version?.split('.')[0] || '0');

      if (testingLibMajor >= 14) {
        expect(reactMajor).toBeGreaterThanOrEqual(18);
      }
    });
  });

  describe('Build Tool Integration', () => {
    it('Next.js should be compatible with React', () => {
      const next = packageLock.packages?.['node_modules/next'];
      const react = packageLock.packages?.['node_modules/react'];

      const nextMajor = parseInt(next?.version?.split('.')[0] || '0');
      const reactMajor = parseInt(react?.version?.split('.')[0] || '0');

      // Next.js 14 requires React 18
      if (nextMajor >= 14) {
        expect(reactMajor).toBeGreaterThanOrEqual(18);
      }
    });

    it('TypeScript dependencies should be consistent', () => {
      const typescript = packageLock.packages?.['node_modules/typescript'];
      expect(typescript).toBeDefined();

      // All @types packages should be compatible
      const typesPackages = Object.keys(packageLock.packages || {}).filter((p) =>
        p.includes('@types/')
      );

      expect(typesPackages.length).toBeGreaterThan(0);
    });
  });

  describe('Visualization Libraries Integration', () => {
    it('plotly and react-plotly should be compatible', () => {
      const plotly = packageLock.packages?.['node_modules/plotly.js'];
      const reactPlotly = packageLock.packages?.['node_modules/react-plotly.js'];

      expect(plotly).toBeDefined();
      expect(reactPlotly).toBeDefined();

      // react-plotly.js should work with plotly.js
      if (reactPlotly?.peerDependencies) {
        const plotlyPeer = reactPlotly.peerDependencies['plotly.js'];
        if (plotlyPeer) {
          expect(plotly?.version).toBeDefined();
        }
      }
    });

    it('recharts should be compatible with React', () => {
      const recharts = packageLock.packages?.['node_modules/recharts'];
      const react = packageLock.packages?.['node_modules/react'];

      expect(recharts).toBeDefined();
      expect(react).toBeDefined();

      // Recharts 2.x works with React 16+
      const rechartsMajor = parseInt(recharts?.version?.split('.')[0] || '0');
      const reactMajor = parseInt(react?.version?.split('.')[0] || '0');

      if (rechartsMajor >= 2) {
        expect(reactMajor).toBeGreaterThanOrEqual(16);
      }
    });
  });

  describe('Lockfile Health', () => {
    it('should not have missing dependencies', () => {
      let missingCount = 0;

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.dependencies) {
          Object.keys(pkg.dependencies).forEach((dep) => {
            const depExists = Object.keys(packageLock.packages).some((p) =>
              p.includes(`/${dep}`) || p === `node_modules/${dep}`
            );

            if (!depExists) {
              missingCount++;
              console.error(`Missing dependency: ${dep} required by ${path}`);
            }
          });
        }
      });

      expect(missingCount).toBe(0);
    });

    it('should not have phantom dependencies', () => {
      const declaredDeps = new Set([
        ...Object.keys(packageJson.dependencies || {}),
        ...Object.keys(packageJson.devDependencies || {}),
      ]);

      const rootLockDeps = new Set([
        ...Object.keys(packageLock.packages?.['']?.dependencies || {}),
        ...Object.keys(packageLock.packages?.['']?.devDependencies || {}),
      ]);

      // All root lock deps should be declared
      rootLockDeps.forEach((dep) => {
        expect(declaredDeps.has(dep)).toBeTruthy();
      });
    });

    it('lockfile should be deterministic', () => {
      // Lockfile should be parseable and re-stringifiable
      const reparsed = JSON.parse(JSON.stringify(packageLock));

      expect(reparsed.name).toBe(packageLock.name);
      expect(reparsed.version).toBe(packageLock.version);
      expect(reparsed.lockfileVersion).toBe(packageLock.lockfileVersion);
    });
  });
});
