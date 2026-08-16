import { existsSync, realpathSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

function containsPath(root, candidate) {
  const relativePath = relative(root, candidate);
  return (
    relativePath === "" ||
    (!isAbsolute(relativePath) && relativePath !== ".." && !relativePath.startsWith(`..${sep}`))
  );
}

export function resolveTurbopackRoot(projectDirectory) {
  const projectRoot = realpathSync(resolve(projectDirectory));
  const nodeModulesLink = join(projectRoot, "node_modules");
  if (!existsSync(nodeModulesLink)) {
    return projectRoot;
  }

  const dependencyRoot = realpathSync(nodeModulesLink);
  let commonRoot = projectRoot;
  while (!containsPath(commonRoot, dependencyRoot)) {
    const parent = dirname(commonRoot);
    if (parent === commonRoot) {
      break;
    }
    commonRoot = parent;
  }
  return commonRoot;
}
