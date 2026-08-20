import { existsSync, readFileSync } from "fs";
import { join } from "path";

type NextConfigContract = {
  typescript?: {
    ignoreBuildErrors?: boolean;
    tsconfigPath?: string;
  };
};

type TypeScriptConfigContract = {
  exclude?: string[];
};

describe("Next.js TypeScript configuration", () => {
  const frontendRoot = process.cwd();
  const nextConfig = jest.requireActual<NextConfigContract>(
    join(frontendRoot, "next.config.js"),
  );
  const tsconfigPath = join(
    frontendRoot,
    nextConfig.typescript?.tsconfigPath ?? "",
  );

  it("uses the production TypeScript project", () => {
    expect(nextConfig.typescript?.tsconfigPath).toBe(
      "tsconfig.typecheck.json",
    );
  });

  it("does not ignore application type errors", () => {
    expect(nextConfig.typescript?.ignoreBuildErrors).not.toBe(true);
  });

  it("references an existing TypeScript project", () => {
    expect(existsSync(tsconfigPath)).toBe(true);
  });

  it("keeps Jest sources outside the production typecheck", () => {
    const tsconfig = JSON.parse(
      readFileSync(tsconfigPath, "utf8"),
    ) as TypeScriptConfigContract;

    expect(tsconfig.exclude).toContain("__tests__");
  });
});
