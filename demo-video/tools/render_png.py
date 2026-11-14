"""Render local HTML/SVG files to 1920x1080 PNGs with headless Chrome (CDP).

usage: render_png.py <ws-url> <in1> <out1> [<in2> <out2> ...]
Files whose name contains 'overlay' or 'sub-' are rendered with a transparent background.
"""

import asyncio
import base64
import json
import sys

import websockets


async def main():
    ws_url, pairs = sys.argv[1], sys.argv[2:]
    async with websockets.connect(ws_url, max_size=None) as ws:
        n = 0

        async def call(method, **params):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    return msg.get("result", {})

        await call("Page.enable")
        await call("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1, mobile=False)
        for src, dst in zip(pairs[::2], pairs[1::2]):
            transparent = "overlay" in src or "sub-" in src
            await call("Emulation.setDefaultBackgroundColorOverride",
                       color={"r": 0, "g": 0, "b": 0, "a": 0} if transparent else {"r": 255, "g": 255, "b": 255, "a": 1})
            await call("Page.navigate", url="file://" + src)
            await asyncio.sleep(0.25)
            await call("Runtime.evaluate", expression="document.fonts.ready.then(() => 1)", awaitPromise=True)
            await asyncio.sleep(0.1)
            shot = await call("Page.captureScreenshot", format="png",
                              clip={"x": 0, "y": 0, "width": 1920, "height": 1080, "scale": 1})
            with open(dst, "wb") as f:
                f.write(base64.b64decode(shot["data"]))


asyncio.run(main())
