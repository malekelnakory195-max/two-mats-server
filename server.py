import asyncio, json, os, random
from http import HTTPStatus
import websockets

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
rooms = {}

def new_code():
    while True:
        code = "".join(random.choices(ALPHABET, k=4))
        if code not in rooms:
            return code

async def send(ws, obj):
    try:
        await ws.send(json.dumps(obj))
    except Exception:
        pass

async def handler(ws):
    code, role = None, None
    try:
        async for raw in ws:
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(m, dict):
                continue
            t = m.get("t")
            if t == "create" and code is None:
                code = new_code(); role = "host"
                rooms[code] = {"host": ws, "guest": None}
                await send(ws, {"t": "created", "code": code})
            elif t == "join" and code is None:
                want = str(m.get("code", "")).upper().strip()
                room = rooms.get(want)
                if room is None:
                    await send(ws, {"t": "error", "msg": "Room not found. Check the code."})
                elif room["guest"] is not None:
                    await send(ws, {"t": "error", "msg": "Room is full."})
                else:
                    room["guest"] = ws; code, role = want, "guest"
                    await send(ws, {"t": "joined"})
                    await send(room["host"], {"t": "peer_joined"})
            elif t == "relay" and code is not None:
                room = rooms.get(code)
                if room:
                    other = room["guest"] if role == "host" else room["host"]
                    if other is not None:
                        await send(other, {"t": "msg", "d": m.get("d")})
    except websockets.ConnectionClosed:
        pass
    finally:
        room = rooms.get(code) if code else None
        if room:
            if role == "host":
                other = room["guest"]; del rooms[code]
            else:
                other = room["host"]; room["guest"] = None
            if other is not None:
                await send(other, {"t": "peer_left"})

async def health(connection, request):
    if request.path == "/healthz":
        resp = connection.respond(HTTPStatus.OK, "ok\n")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
    return None

async def main():
    port = int(os.environ.get("PORT", "8765"))
    async with websockets.serve(handler, "0.0.0.0", port, max_size=2**16, process_request=health):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
