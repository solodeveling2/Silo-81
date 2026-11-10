import io, sys, zipfile, requests
URL = sys.argv[1]; WANT = sys.argv[2:]
s = requests.Session()
r = s.get(URL, headers={"Range": "bytes=0-0"}, allow_redirects=True)
total = int(r.headers["Content-Range"].split("/")[1]); final = r.url
class RF(io.RawIOBase):
    def __init__(self): self.pos = 0; self.cache = {}
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else total + off); return self.pos
    def read(self, n=-1):
        if n is None or n < 0: n = total - self.pos
        if n == 0 or self.pos >= total: return b""
        end = min(total, self.pos + n) - 1
        rr = s.get(final, headers={"Range": f"bytes={self.pos}-{end}"})
        if rr.status_code not in (200, 206): raise IOError(rr.status_code)
        d = rr.content; self.pos += len(d); return d
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)
f = io.BufferedReader(RF(), buffer_size=1 << 20)
z = zipfile.ZipFile(f)
if not WANT:
    for i in z.infolist():
        if "web" in i.filename or "version" in i.filename: print(i.filename, i.file_size, i.compress_size)
else:
    for w in WANT:
        data = z.read(w); open(w.split("/")[-1], "wb").write(data); print("saved", w, len(data))
