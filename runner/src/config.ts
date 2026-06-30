export interface HarnessConfig {
  appUrl: string;
  username: string;
  password: string;
  beUploadsDir: string;
  workspaceRoot: string;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): HarnessConfig {
  const workspaceRoot = env.PT_WORKSPACE ?? "/Users/parker/workspaces/plextrac";
  return {
    appUrl: env.PT_APP_URL ?? "https://plextrac.localhost",
    username: env.PT_TEST_USER ?? "global_admin",
    password: env.PT_TEST_PASS ?? "password",
    beUploadsDir: env.PT_BE_UPLOADS ?? `${workspaceRoot}/product-core-backend/uploads`,
    workspaceRoot,
  };
}
