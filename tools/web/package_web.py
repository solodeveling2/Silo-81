"""Turn a Godot web export into files the artifact host accepts: the 35 MB engine gzipped into
engine.wasm and the game pack split into <16 MB parts named pack0.wasm, pack1.wasm, ...
A small loader in index.html rebuilds both before Godot fetches them.
Usage: python3 package_web.py export_dir site_dir"""
import sys, os, gzip, shutil
src, dst = sys.argv[1], sys.argv[2]
shutil.rmtree(dst, ignore_errors=True); os.makedirs(dst)
for f in ("index.js", "index.audio.worklet.js", "index.png", "index.icon.png", "index.apple-touch-icon.png"):
    shutil.copy(os.path.join(src, f), dst)
with open(os.path.join(src, "index.wasm"), "rb") as fi, gzip.open(os.path.join(dst, "engine.wasm"), "wb", 9) as fo:
    shutil.copyfileobj(fi, fo)
data = open(os.path.join(src, "index.pck"), "rb").read()
CH = 16_000_000
parts = []
for i in range(0, len(data), CH):
    name = f"pack{len(parts)}.wasm"
    open(os.path.join(dst, name), "wb").write(data[i:i + CH]); parts.append(name)
html = open(os.path.join(src, "index.html")).read()
loader = '''<script>
(function () {
  // The host caps single files at 20 MiB, so the engine is stored gzipped and the game pack
  // in parts; this rebuilds both before Godot sees them.
  var realFetch = window.fetch.bind(window);
  var parts = { "index.pck": %s };
  function get(url) {
    return realFetch(url).then(function (r) {
      if (!r.ok) throw new Error("Could not load " + url + " (" + r.status + ")");
      return r;
    });
  }
  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var name = url.split("/").pop().split("?")[0];
    if (name === "index.wasm") {
      return get("engine.wasm").then(function (r) {
        var body = r.body.pipeThrough(new DecompressionStream("gzip"));
        return new Response(body, { status: 200, headers: { "Content-Type": "application/wasm" } });
      });
    }
    if (parts[name]) {
      return Promise.all(parts[name].map(function (p) {
        return get(p).then(function (r) { return r.blob(); });
      })).then(function (blobs) {
        return new Response(new Blob(blobs), { status: 200, headers: { "Content-Type": "application/octet-stream" } });
      });
    }
    return realFetch(input, init);
  };
})();
</script>
''' % str(parts).replace("'", '"')
html = html.replace('<script src="index.js"></script>', loader + '\t\t<script src="index.js"></script>', 1)
html = html.replace('"ensureCrossOriginIsolationHeaders":true', '"ensureCrossOriginIsolationHeaders":false')
open(os.path.join(dst, "index.html"), "w").write(html)
for f in sorted(os.listdir(dst)):
    print(f, os.path.getsize(os.path.join(dst, f)))
