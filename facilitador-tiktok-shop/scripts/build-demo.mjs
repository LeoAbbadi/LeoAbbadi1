// Gera a versão de demonstração (sem servidor) num único arquivo HTML,
// pronta para publicar como prévia: dist-demo/facilitador-demo.html
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const out = path.resolve("dist-demo");
execSync(`npx vite build --outDir ${out} --base ./ --emptyOutDir`, {
  stdio: "inherit",
  env: { ...process.env, VITE_DEMO: "1" },
});

let html = fs.readFileSync(path.join(out, "index.html"), "utf8");
const read = (ref) => fs.readFileSync(path.join(out, ref.replace(/^\.\//, "")), "utf8");

// CSS e JS embutidos no próprio HTML
html = html.replace(/<link rel="stylesheet"[^>]*href="([^"]+)"[^>]*>/g, (_, href) => `<style>\n${read(href)}\n</style>`);
html = html.replace(/<script type="module"[^>]*src="([^"]+)"[^>]*><\/script>/g, (_, src) => {
  const js = read(src).replace(/<\/script/gi, "<\\/script");
  return `<script type="module">\n${js}\n</script>`;
});
const favicon = fs.readFileSync(path.join(out, "favicon.svg"));
html = html.replace(/href="\.\/favicon\.svg"/, `href="data:image/svg+xml;base64,${favicon.toString("base64")}"`);
html = html.replace(/<link rel="modulepreload"[^>]*>/g, "");

// A prévia já envolve a página em <html>/<head>/<body>: guarda só o conteúdo
const head = html.match(/<head>([\s\S]*)<\/head>/)[1].replace(/<meta charset[^>]*>|<meta name="viewport"[^>]*>/g, "");
const body = html.match(/<body>([\s\S]*)<\/body>/)[1];
const page = `${head.trim()}\n${body.trim()}\n`;
fs.writeFileSync(path.join(out, "facilitador-demo.html"), page);
console.log(`Demonstração gerada: dist-demo/facilitador-demo.html (${Math.round(page.length / 1024)} KB)`);
