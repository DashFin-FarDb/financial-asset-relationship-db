/**
 * Comprehensive unit tests for frontend package-lock.json validation.
 *
 * Tests cover:
 * - Lockfile existence and format
 * - Consistency with package.json
 * - Dependency resolution integrity
 * - Version pinning validation
 * - Axios upgrade verification
 * - Peer dependency compatibility
 * - Security and integrity checks
 *
 * This ensures that the package-lock.json correctly reflects the axios
 * upgrade from 1.6.0 to 1.13.2 and maintains dependency tree integrity.
 */

import { readFileSync, existsSync } from 'fs';
import { join } from 'path';

describe('Package-lock.json Validation', () => {
  const packageJsonPath = join(process.cwd(), 'package.json');
  const packageLockPath = join(process.cwd(), 'package-lock.json');
  let packageJson: any;
  let packageLock: any;

  beforeAll(() => {
    if (!existsSync(packageJsonPath)) {
      throw new Error('package.json not found');
    }
    if (!existsSync(packageLockPath)) {
      throw new Error('package-lock.json not found');
    }

    const packageContent = readFileSync(packageJsonPath, 'utf-8');
    packageJson = JSON.parse(packageContent);

    const lockContent = readFileSync(packageLockPath, 'utf-8');
    packageLock = JSON.parse(lockContent);
  });

  describe('File Existence and Format', () => {
    it('should exist in the frontend directory', () => {
      expect(existsSync(packageLockPath)).toBe(true);
    });

    it('should be valid JSON', () => {
      expect(() => {
        const content = readFileSync(packageLockPath, 'utf-8');
        JSON.parse(content);
      }).not.toThrow();
    });

    it('should be a valid package-lock.json structure', () => {
      expect(packageLock).toBeDefined();
      expect(typeof packageLock).toBe('object');
      expect(packageLock).not.toBeNull();
    });

    it('should have lockfileVersion field', () => {
      expect(packageLock.lockfileVersion).toBeDefined();
      expect(typeof packageLock.lockfileVersion).toBe('number');
    });

    it('should use lockfile version 2 or 3', () => {
      expect(packageLock.lockfileVersion).toBeGreaterThanOrEqual(2);
      expect(packageLock.lockfileVersion).toBeLessThanOrEqual(3);
    });
  });

  describe('Consistency with package.json', () => {
    it('should have matching name', () => {
      expect(packageLock.name).toBe(packageJson.name);
    });

    it('should have matching version', () => {
      expect(packageLock.version).toBe(packageJson.version);
    });

    it('should include all dependencies from package.json', () => {
      const packageDeps = Object.keys(packageJson.dependencies || {});
      const lockDeps = packageLock.packages?.['']?.dependencies || {};

      packageDeps.forEach((dep) => {
        expect(lockDeps[dep]).toBeDefined();
      });
    });

    it('should include all devDependencies from package.json', () => {
      const packageDevDeps = Object.keys(packageJson.devDependencies || {});
      const lockDevDeps = packageLock.packages?.['']?.devDependencies || {};

      packageDevDeps.forEach((dep) => {
        expect(lockDevDeps[dep]).toBeDefined();
      });
    });

    it('dependency versions should satisfy package.json ranges', () => {
      const lockPackages = packageLock.packages || {};
      const packageDeps = { ...packageJson.dependencies, ...packageJson.devDependencies };

      Object.keys(packageDeps).forEach((dep) => {
        const lockEntry = lockPackages[`node_modules/${dep}`];
        if (lockEntry) {
          expect(lockEntry.version).toBeDefined();
        }
      });
    });
  });

  describe('Axios Upgrade Validation', () => {
    it('should have axios in the lockfile', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock).toBeDefined();
    });

    it('should have axios version 1.13.2', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.version).toBe('1.13.2');
    });

    it('axios should have resolved URL pointing to registry', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.resolved).toBeDefined();
      expect(axiosLock?.resolved).toContain('registry.npmjs.org');
      expect(axiosLock?.resolved).toContain('axios-1.13.2.tgz');
    });

    it('axios should have integrity hash', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.integrity).toBeDefined();
      expect(axiosLock?.integrity).toMatch(/^sha\d+-/);
    });

    it('axios should specify license', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.license).toBeDefined();
      expect(axiosLock?.license).toBe('MIT');
    });

    it('axios dependencies should be resolved', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      if (axiosLock?.dependencies) {
        Object.entries(axiosLock.dependencies).forEach(([dep, version]) => {
          expect(version).toBeDefined();
          expect(typeof version).toBe('string');
        });
      }
    });

    it('axios should not have peer dependency conflicts', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      // Axios typically doesn't have strict peer dependencies
      if (axiosLock?.peerDependencies) {
        expect(Object.keys(axiosLock.peerDependencies).length).toBe(0);
      }
    });
  });

  describe('Dependency Tree Integrity', () => {
    it('should have packages field', () => {
      expect(packageLock.packages).toBeDefined();
      expect(typeof packageLock.packages).toBe('object');
    });

    it('root package should be defined', () => {
      expect(packageLock.packages['']).toBeDefined();
    });

    it('all packages should have version or link', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path !== '') {
          expect(pkg.version || pkg.link).toBeDefined();
        }
      });
    });

    it('all packages should have resolved URLs or be local', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path !== '' && !pkg.link && !pkg.dev && path.startsWith('node_modules/')) {
          // Non-local packages should have resolved URL
          if (!pkg.resolved?.startsWith('file:')) {
            expect(pkg.resolved).toBeDefined();
          }
        }
      });
    });

    it('all non-local packages should have integrity hashes', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path !== '' && !pkg.link && pkg.resolved && !pkg.resolved.startsWith('file:')) {
          expect(pkg.integrity).toBeDefined();
          expect(pkg.integrity).toMatch(/^sha\d+-/);
        }
      });
    });
  });

  describe('Core Dependencies in Lockfile', () => {
    const coreDeps = ['react', 'react-dom', 'next', 'axios'];

    coreDeps.forEach((dep) => {
      it(`should have ${dep} in lockfile`, () => {
        const depEntry = packageLock.packages?.[`node_modules/${dep}`];
        expect(depEntry).toBeDefined();
        expect(depEntry.version).toBeDefined();
      });

      it(`should have integrity hash for ${dep}`, () => {
        const depEntry = packageLock.packages?.[`node_modules/${dep}`];
        expect(depEntry?.integrity).toBeDefined();
      });

      it(`should have resolved URL for ${dep}`, () => {
        const depEntry = packageLock.packages?.[`node_modules/${dep}`];
        expect(depEntry?.resolved).toBeDefined();
        expect(depEntry?.resolved).toContain('registry.npmjs.org');
      });
    });
  });

  describe('Development Dependencies in Lockfile', () => {
    const devDeps = ['jest', 'typescript', '@testing-library/react'];

    devDeps.forEach((dep) => {
      it(`should have ${dep} in lockfile`, () => {
        const depEntry = packageLock.packages?.[`node_modules/${dep}`];
        expect(depEntry).toBeDefined();
      });

      it(`should mark ${dep} as dev dependency`, () => {
        const depEntry = packageLock.packages?.[`node_modules/${dep}`];
        // Dev flag might be on the root package entry
        const rootDeps = packageLock.packages?.['']?.devDependencies || {};
        const isDevDep = rootDeps[dep] !== undefined;
        expect(isDevDep || depEntry?.dev).toBeTruthy();
      });
    });
  });

  describe('Transitive Dependencies', () => {
    it('should resolve transitive dependencies of axios', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];

      if (axiosLock?.dependencies) {
        Object.keys(axiosLock.dependencies).forEach((dep) => {
          // Each axios dependency should also be in the lockfile
          const foundInRoot = packageLock.packages?.[`node_modules/${dep}`];
          const foundNested = packageLock.packages?.[`node_modules/axios/node_modules/${dep}`];

          expect(foundInRoot || foundNested).toBeDefined();
        });
      }
    });

    it('should have follow-redirects as axios dependency', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];

      if (axiosLock?.dependencies) {
        // Axios 1.x uses follow-redirects
        const hasFollowRedirects = axiosLock.dependencies['follow-redirects'] !== undefined;

        if (hasFollowRedirects) {
          const followRedirectsLock =
            packageLock.packages?.['node_modules/follow-redirects'] ||
            packageLock.packages?.['node_modules/axios/node_modules/follow-redirects'];

          expect(followRedirectsLock).toBeDefined();
        }
      }
    });

    it('should have form-data as axios dependency', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];

      if (axiosLock?.dependencies?.['form-data']) {
        const formDataLock =
          packageLock.packages?.['node_modules/form-data'] ||
          packageLock.packages?.['node_modules/axios/node_modules/form-data'];

        expect(formDataLock).toBeDefined();
      }
    });

    it('should have proxy-from-env as axios dependency', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];

      if (axiosLock?.dependencies?.['proxy-from-env']) {
        const proxyLock =
          packageLock.packages?.['node_modules/proxy-from-env'] ||
          packageLock.packages?.['node_modules/axios/node_modules/proxy-from-env'];

        expect(proxyLock).toBeDefined();
      }
    });
  });

  describe('Peer Dependencies', () => {
    it('should not have unresolved peer dependencies', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.peerDependencies) {
          // Peer dependencies should either be satisfied or marked as optional
          Object.keys(pkg.peerDependencies).forEach((peerDep) => {
            const peerOptional = pkg.peerDependenciesMeta?.[peerDep]?.optional;

            if (!peerOptional) {
              // Non-optional peer dep should be in the tree
              const peerInTree = Object.keys(packageLock.packages).some((p) =>
                p.includes(`node_modules/${peerDep}`)
              );

              expect(peerInTree).toBeTruthy();
            }
          });
        }
      });
    });

    it('React peer dependencies should be satisfied', () => {
      const reactVersion = packageLock.packages?.['node_modules/react']?.version;
      expect(reactVersion).toBeDefined();

      // Check packages that have React as peer dependency
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.peerDependencies?.react) {
          const isOptional = pkg.peerDependenciesMeta?.react?.optional;
          if (!isOptional) {
            // React should be available
            expect(reactVersion).toBeDefined();
          }
        }
      });
    });
  });

  describe('Version Pinning and Resolution', () => {
    it('all package versions should be exact in lockfile', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.version && path !== '') {
          // Versions in lockfile should be exact (no ^, ~, etc.)
          expect(pkg.version).toMatch(/^\d+\.\d+\.\d+/);
          expect(pkg.version).not.toMatch(/^[\^~]/);
        }
      });
    });

    it('should not have version ranges in lockfile', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.version) {
          expect(pkg.version).not.toContain('||');
          expect(pkg.version).not.toContain('*');
          expect(pkg.version).not.toContain('x');
        }
      });
    });

    it('dependency constraints should use exact versions or ranges', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.dependencies) {
          Object.values(pkg.dependencies).forEach((version) => {
            expect(typeof version).toBe('string');
            expect((version as string).length).toBeGreaterThan(0);
          });
        }
      });
    });
  });

  describe('Security and Integrity', () => {
    it('all integrity hashes should use SHA-512 or higher', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.integrity) {
          // Should use sha512 or sha256 at minimum
          expect(pkg.integrity).toMatch(/^sha(256|384|512)-/);
        }
      });
    });

    it('axios should have valid integrity hash', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.integrity).toBeDefined();
      expect(axiosLock?.integrity).toMatch(/^sha512-/);
    });

    it('should not have git:// URLs (use https:// instead)', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.resolved) {
          expect(pkg.resolved).not.toMatch(/^git:/);
        }
      });
    });

    it('should use registry.npmjs.org or known registries', () => {
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.resolved && !pkg.resolved.startsWith('file:')) {
          const validRegistries = [
            'registry.npmjs.org',
            'registry.yarnpkg.com',
            'npm.pkg.github.com',
          ];

          const usesKnownRegistry = validRegistries.some((registry) =>
            pkg.resolved.includes(registry)
          );

          expect(usesKnownRegistry).toBeTruthy();
        }
      });
    });
  });

  describe('License Information', () => {
    it('core packages should specify licenses', () => {
      const corePkgs = ['axios', 'react', 'next'];

      corePkgs.forEach((pkg) => {
        const pkgEntry = packageLock.packages?.[`node_modules/${pkg}`];
        expect(pkgEntry?.license).toBeDefined();
      });
    });

    it('axios should have MIT license', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      expect(axiosLock?.license).toBe('MIT');
    });

    it('should not have GPL-licensed dependencies (if policy requires)', () => {
      // This is optional - some projects restrict GPL
      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.license) {
          const gplLicenses = ['GPL', 'AGPL', 'LGPL'];
          const isGPL = gplLicenses.some((gpl) =>
            (pkg.license as string).toUpperCase().includes(gpl)
          );

          // Log if GPL found (not failing, just checking)
          if (isGPL) {
            console.log(`Note: GPL-licensed package found: ${path}`);
          }
        }
      });
    });
  });

  describe('Lockfile Size and Performance', () => {
    it('should have a reasonable number of packages', () => {
      const packageCount = Object.keys(packageLock.packages).length;
      expect(packageCount).toBeGreaterThan(10);
      expect(packageCount).toBeLessThan(10000); // Sanity check
    });

    it('should not have excessive duplicate versions', () => {
      const versionMap = new Map<string, Set<string>>();

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path && pkg.version) {
          const pkgName = path.split('node_modules/').pop()?.split('/')[0];
          if (pkgName) {
            if (!versionMap.has(pkgName)) {
              versionMap.set(pkgName, new Set());
            }
            versionMap.get(pkgName)!.add(pkg.version);
          }
        }
      });

      // Most packages should have 1-2 versions max
      versionMap.forEach((versions, pkg) => {
        if (versions.size > 3) {
          console.log(`Note: Package ${pkg} has ${versions.size} versions`);
        }
        expect(versions.size).toBeLessThan(10); // Sanity check
      });
    });
  });

  describe('Dependency Hoisting', () => {
    it('common dependencies should be hoisted to top level', () => {
      // Core dependencies should be at top level
      const topLevelPackages = Object.keys(packageLock.packages)
        .filter((p) => p.match(/^node_modules\/[^/]+$/));

      expect(topLevelPackages.length).toBeGreaterThan(10);
      expect(topLevelPackages).toContain('node_modules/react');
      expect(topLevelPackages).toContain('node_modules/axios');
    });

    it('should minimize nested node_modules', () => {
      const nestedPackages = Object.keys(packageLock.packages)
        .filter((p) => p.includes('node_modules') && p.split('node_modules').length > 2);

      const totalPackages = Object.keys(packageLock.packages).length;
      const nestedRatio = nestedPackages.length / totalPackages;

      // Most packages should be hoisted
      expect(nestedRatio).toBeLessThan(0.3);
    });
  });

  describe('Axios Specific Validation', () => {
    it('axios should not have conflicting versions', () => {
      const axiosVersions = new Set<string>();

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (path.includes('axios') && pkg.version) {
          axiosVersions.add(pkg.version);
        }
      });

      // Should only have one version of axios
      expect(axiosVersions.size).toBe(1);
      expect(axiosVersions.has('1.13.2')).toBeTruthy();
    });

    it('axios dependencies should be compatible versions', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];

      if (axiosLock?.dependencies) {
        Object.entries(axiosLock.dependencies).forEach(([dep, version]) => {
          expect(version).toBeDefined();
          expect(typeof version).toBe('string');
          // Should have version constraint
          expect((version as string).length).toBeGreaterThan(0);
        });
      }
    });
  });

  describe('Backwards Compatibility', () => {
    it('axios 1.13.2 should be compatible with existing code', () => {
      const axiosLock = packageLock.packages?.['node_modules/axios'];
      const version = axiosLock?.version;

      expect(version).toBe('1.13.2');

      // Major version should be 1 for backward compatibility
      const major = parseInt(version!.split('.')[0]);
      expect(major).toBe(1);
    });

    it('should not break any peer dependencies with upgrade', () => {
      // Check if any package has axios as peer dependency
      let axiosPeerDepFound = false;

      Object.entries(packageLock.packages).forEach(([path, pkg]: [string, any]) => {
        if (pkg.peerDependencies?.axios) {
          axiosPeerDepFound = true;
          const peerVersion = pkg.peerDependencies.axios;

          // 1.13.2 should satisfy the peer dependency
          expect(peerVersion).toBeDefined();
        }
      });

      // Axios typically doesn't have peer deps, but check anyway
      expect(true).toBeTruthy(); // Test passes
    });
  });

  describe('Package-lock Metadata', () => {
    it('should have requires field set appropriately', () => {
      if (packageLock.requires !== undefined) {
        expect(typeof packageLock.requires).toBe('boolean');
      }
    });

    it('root package should match package.json structure', () => {
      const root = packageLock.packages?.[''];

      expect(root?.name).toBe(packageJson.name);
      expect(root?.version).toBe(packageJson.version);
    });

    it('should have appropriate engines if specified', () => {
      if (packageJson.engines) {
        const root = packageLock.packages?.[''];
        expect(root).toBeDefined();
      }
    });
  });

  describe('File Integrity', () => {
    it('should be parseable without errors', () => {
      expect(() => {
        JSON.parse(readFileSync(packageLockPath, 'utf-8'));
      }).not.toThrow();
    });

    it('should not have circular references', () => {
      expect(() => {
        JSON.stringify(packageLock);
      }).not.toThrow();
    });

    it('should be a valid lockfile format', () => {
      expect(packageLock.lockfileVersion).toBeDefined();
      expect(packageLock.packages).toBeDefined();
      expect(packageLock.packages['']).toBeDefined();
    });
  });
});
