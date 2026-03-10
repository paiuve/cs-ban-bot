"""
Discord Bot — CS:GO Ban System
Butoane + Formulare (Modals) pentru admin management si unban

Instalare:
    pip install discord.py mysql-connector-python python-dotenv

Configurare: seteaza variabilele de mediu in Render Environment Variables
    DISCORD_TOKEN, DB_HOST, DB_USER, DB_PASS, DB_NAME, ADMIN_ROLE_ID, PANEL_CHANNEL_ID
"""

import discord
import asyncio
from discord.ext import commands
from discord import app_commands, ui
import mysql.connector
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TOKEN            = os.getenv("DISCORD_TOKEN")
DB_HOST          = os.getenv("DB_HOST")
DB_USER          = os.getenv("DB_USER")
DB_PASS          = os.getenv("DB_PASS")
DB_NAME          = os.getenv("DB_NAME")
ADMIN_ROLE_ID    = int(os.getenv("ADMIN_ROLE_ID",    "0"))
PANEL_CHANNEL_ID = int(os.getenv("PANEL_CHANNEL_ID", "0"))

# ─── Bot ─────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ─── DB ──────────────────────────────────────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

def is_authorized(interaction: discord.Interaction) -> bool:
    if ADMIN_ROLE_ID == 0:
        return True
    return any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles)

# ─────────────────────────────────────────────────────────────────────────────
# MODALS (formulare popup)
# ─────────────────────────────────────────────────────────────────────────────

class AddAdminModal(ui.Modal, title="➕ Adaugă Admin"):
    steamid   = ui.TextInput(label="SteamID",   placeholder="STEAM_0:1:12345678", min_length=5, max_length=32)
    name      = ui.TextInput(label="Nume",       placeholder="Numele jucatorului", min_length=1, max_length=64)
    immunity  = ui.TextInput(label="Imunitate",  placeholder="0-100 (ex: 50)",    min_length=1, max_length=3, default="50")
    flags     = ui.TextInput(label="Flags",      placeholder="b=ban d=kick e=slay z=root (ex: bd)", min_length=1, max_length=32, default="bd")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            imm = int(str(self.immunity))
        except:
            await interaction.response.send_message("❌ Imunitatea trebuie sa fie un numar (0-100).", ephemeral=True)
            return

        try:
            db  = get_db()
            cur = db.cursor()
            cur.execute(
                """INSERT INTO ban_admins (steamid, name, flags, immunity, added_by, added_time)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE name=%s, flags=%s, immunity=%s, added_by=%s""",
                (str(self.steamid), str(self.name), str(self.flags), imm,
                 str(interaction.user), int(datetime.now().timestamp()),
                 str(self.name), str(self.flags), imm, str(interaction.user))
            )
            db.commit()
            cur.close()
            db.close()

            embed = discord.Embed(title="✅ Admin Adăugat", color=0x57f287, timestamp=datetime.now())
            embed.add_field(name="👤 Nume",        value=str(self.name),     inline=True)
            embed.add_field(name="🆔 SteamID",     value=str(self.steamid),  inline=True)
            embed.add_field(name="🛡️ Imunitate",   value=str(imm),           inline=True)
            embed.add_field(name="🔑 Flags",        value=f"`{self.flags}`",  inline=True)
            embed.add_field(name="➕ Adăugat de",   value=str(interaction.user), inline=True)
            embed.set_footer(text="Foloseste sm_reloadadmins pe server pentru a aplica imediat")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Eroare DB: `{e}`", ephemeral=True)


class DelAdminModal(ui.Modal, title="🗑️ Șterge Admin"):
    steamid = ui.TextInput(label="SteamID", placeholder="STEAM_0:1:12345678", min_length=5, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            db  = get_db()
            cur = db.cursor()
            cur.execute("SELECT name FROM ban_admins WHERE steamid=%s", (str(self.steamid),))
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message(f"⚠️ SteamID `{self.steamid}` nu a fost găsit.", ephemeral=True)
                cur.close(); db.close()
                return

            admin_name = row[0]
            cur.execute("DELETE FROM ban_admins WHERE steamid=%s", (str(self.steamid),))
            db.commit()
            cur.close()
            db.close()

            embed = discord.Embed(title="🗑️ Admin Șters", color=0xed4245, timestamp=datetime.now())
            embed.add_field(name="👤 Nume",       value=admin_name,         inline=True)
            embed.add_field(name="🆔 SteamID",    value=str(self.steamid),  inline=True)
            embed.add_field(name="👮 Șters de",   value=str(interaction.user), inline=True)
            embed.set_footer(text="Foloseste sm_reloadadmins pe server pentru a aplica imediat")
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Eroare DB: `{e}`", ephemeral=True)


class UnbanModal(ui.Modal, title="✅ Dezbaneaza Jucator"):
    steamid = ui.TextInput(label="SteamID", placeholder="STEAM_0:1:12345678", min_length=5, max_length=32)
    reason  = ui.TextInput(label="Motiv unban (optional)", placeholder="ex: ban gresit", required=False, max_length=128)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            db  = get_db()
            cur = db.cursor()

            # Cauta ban activ
            cur.execute(
                "SELECT name, reason FROM bans WHERE steamid=%s AND active=1 LIMIT 1",
                (str(self.steamid),)
            )
            row = cur.fetchone()
            if not row:
                await interaction.response.send_message(f"⚠️ Nu exista ban activ pentru `{self.steamid}`.", ephemeral=True)
                cur.close(); db.close()
                return

            player_name  = row[0]
            ban_reason   = row[1]
            unban_reason = str(self.reason) if self.reason.value else "Dezbanat de admin"

            cur.execute(
                "UPDATE bans SET active=0, unbanned_by=%s WHERE steamid=%s AND active=1",
                (f"{interaction.user} — {unban_reason}", str(self.steamid))
            )
            db.commit()
            cur.close()
            db.close()

            embed = discord.Embed(title="✅ Jucator Dezbanat", color=0x57f287, timestamp=datetime.now())
            embed.add_field(name="👤 Jucator",        value=player_name,        inline=True)
            embed.add_field(name="🆔 SteamID",        value=str(self.steamid),  inline=True)
            embed.add_field(name="🚩 Ban original",   value=ban_reason,         inline=False)
            embed.add_field(name="📝 Motiv unban",    value=unban_reason,       inline=False)
            embed.add_field(name="👮 Dezbanat de",    value=str(interaction.user), inline=True)
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Eroare DB: `{e}`", ephemeral=True)


class BanSearchModal(ui.Modal, title="🔍 Caută Ban-uri"):
    steamid = ui.TextInput(label="SteamID (gol = ultimele 10 banuri)", required=False, max_length=32)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            db  = get_db()
            cur = db.cursor()
            sid = str(self.steamid).strip()

            if sid:
                cur.execute(
                    "SELECT name, reason, duration, ban_time, active, admin_name FROM bans "
                    "WHERE steamid=%s ORDER BY ban_time DESC LIMIT 10", (sid,)
                )
            else:
                cur.execute(
                    "SELECT name, reason, duration, ban_time, active, admin_name FROM bans "
                    "ORDER BY ban_time DESC LIMIT 10"
                )

            rows = cur.fetchall()
            cur.close()
            db.close()

            if not rows:
                await interaction.response.send_message("📋 Nu am găsit ban-uri.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔨 Ban History" + (f" — {sid}" if sid else ""),
                color=0xff6600,
                timestamp=datetime.now()
            )
            for row in rows:
                name, reason, duration, ban_time, active, admin = row
                dur  = "PERMANENT" if duration == 0 else f"{duration} min"
                date = datetime.fromtimestamp(ban_time).strftime("%d/%m/%Y %H:%M")
                st   = "🔴 Activ" if active else "✅ Expirat/Dezbanat"
                embed.add_field(
                    name=f"{st} — {name}",
                    value=f"**Motiv:** {reason}\n**Durata:** {dur} | **Data:** {date} | **Admin:** {admin}",
                    inline=False
                )
            embed.set_footer(text=f"Total rezultate: {len(rows)}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Eroare DB: `{e}`", ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW — Panoul de control cu butoane
# ─────────────────────────────────────────────────────────────────────────────

class ControlPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent — nu expira niciodata

    @ui.button(label="➕ Adaugă Admin", style=discord.ButtonStyle.success, custom_id="btn_add_admin", row=0)
    async def add_admin(self, interaction: discord.Interaction, button: ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("❌ Nu ai permisiunea.", ephemeral=True)
            return
        await interaction.response.send_modal(AddAdminModal())

    @ui.button(label="🗑️ Șterge Admin", style=discord.ButtonStyle.danger, custom_id="btn_del_admin", row=0)
    async def del_admin(self, interaction: discord.Interaction, button: ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("❌ Nu ai permisiunea.", ephemeral=True)
            return
        await interaction.response.send_modal(DelAdminModal())

    @ui.button(label="📋 Listă Admini", style=discord.ButtonStyle.primary, custom_id="btn_list_admins", row=0)
    async def list_admins(self, interaction: discord.Interaction, button: ui.Button):
        try:
            db  = get_db()
            cur = db.cursor()
            cur.execute("SELECT steamid, name, flags, immunity, added_by FROM ban_admins ORDER BY immunity DESC")
            rows = cur.fetchall()
            cur.close(); db.close()

            if not rows:
                await interaction.response.send_message("📋 Nu există admini în baza de date.", ephemeral=True)
                return

            embed = discord.Embed(title="👮 Lista Admini", color=0x3498db, timestamp=datetime.now())
            for steamid, name, flags, immunity, added_by in rows:
                embed.add_field(
                    name=f"🔹 {name}",
                    value=f"**SteamID:** `{steamid}`\n**Flags:** `{flags}` | **Imunitate:** `{immunity}`\n**Adăugat de:** {added_by}",
                    inline=False
                )
            embed.set_footer(text=f"Total: {len(rows)} admini")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Eroare DB: `{e}`", ephemeral=True)

    @ui.button(label="✅ Unban", style=discord.ButtonStyle.success, custom_id="btn_unban", row=1)
    async def unban(self, interaction: discord.Interaction, button: ui.Button):
        if not is_authorized(interaction):
            await interaction.response.send_message("❌ Nu ai permisiunea.", ephemeral=True)
            return
        await interaction.response.send_modal(UnbanModal())

    @ui.button(label="🔍 Caută Ban-uri", style=discord.ButtonStyle.secondary, custom_id="btn_search_bans", row=1)
    async def search_bans(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(BanSearchModal())


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    bot.add_view(ControlPanel())  # re-register persistent view
    await bot.tree.sync()
    print(f"[Bot] Online ca {bot.user}")

    # Trimite panoul de control in canalul setat
    if PANEL_CHANNEL_ID != 0:
        channel = bot.get_channel(PANEL_CHANNEL_ID)
        if channel:
            # Sterge mesajele vechi ale botului din canal
            async for msg in channel.history(limit=20):
                if msg.author == bot.user:
                    try:
                        await msg.delete()
                        await asyncio.sleep(1.0)
                    except discord.HTTPException:
                        pass

            embed = discord.Embed(
                title="🎮 CS:GO Admin Panel — BC.LaLeagane.ro",
                description=(
                    "Foloseste butoanele de mai jos pentru a gestiona adminii si ban-urile.\n\n"
                    "➕ **Adaugă Admin** — completezi SteamID, nume, imunitate, flags\n"
                    "🗑️ **Șterge Admin** — introduci SteamID-ul adminului de sters\n"
                    "📋 **Listă Admini** — vezi toti adminii activi\n"
                    "✅ **Unban** — dezbanezi un jucator dupa SteamID\n"
                    "🔍 **Caută Ban-uri** — cauta in istoricul ban-urilor"
                ),
                color=0x5865f2,
                timestamp=datetime.now()
            )
            embed.set_footer(text="BC.LaLeagane.ro | 128 TICK | Panoul se actualizeaza automat")
            await channel.send(embed=embed, view=ControlPanel())


# ─────────────────────────────────────────────────────────────────────────────
# Slash command sa retrimiti panoul daca e nevoie
# ─────────────────────────────────────────────────────────────────────────────

@bot.tree.command(name="panel", description="Trimite panoul de control CS:GO")
async def panel(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ Nu ai permisiunea.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎮 CS:GO Admin Panel — BC.LaLeagane.ro",
        description=(
            "Foloseste butoanele de mai jos pentru a gestiona adminii si ban-urile.\n\n"
            "➕ **Adaugă Admin** — completezi SteamID, nume, imunitate, flags\n"
            "🗑️ **Șterge Admin** — introduci SteamID-ul adminului de sters\n"
            "📋 **Listă Admini** — vezi toti adminii activi\n"
            "✅ **Unban** — dezbanezi un jucator dupa SteamID\n"
            "🔍 **Caută Ban-uri** — cauta in istoricul ban-urilor"
        ),
        color=0x5865f2,
        timestamp=datetime.now()
    )
    embed.set_footer(text="BC.LaLeagane.ro | 128 TICK")
    await interaction.response.send_message(embed=embed, view=ControlPanel())


# ─────────────────────────────────────────────────────────────────────────────
# /setup — creaza canalele necesare intr-o categorie selectata
# ─────────────────────────────────────────────────────────────────────────────

@bot.tree.command(name="setup", description="Creeaza canalele necesare pentru sistemul de ban")
@app_commands.describe(category="Categoria unde sa fie create canalele")
async def setup(interaction: discord.Interaction, category: discord.CategoryChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Doar administratorii pot face setup.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    channels_to_create = [
        {"name": "🔨・bans",        "topic": "Notificari automate ban-uri noi"},
        {"name": "✅・unbans",       "topic": "Notificari automate unban-uri"},
        {"name": "👮・admins-log",   "topic": "Loguri adaugare/stergere admini"},
        {"name": "📋・ban-history",  "topic": "Istoricul ban-urilor"},
        {"name": "🎮・admin-panel",  "topic": "Panoul de control CS:GO"},
    ]

    created = []
    skipped = []
    channel_ids = {}

    existing = {ch.name: ch for ch in category.channels}

    for ch_info in channels_to_create:
        name = ch_info["name"]
        if name in existing:
            skipped.append(name)
            channel_ids[name] = existing[name].id
            continue

        try:
            new_ch = await category.create_text_channel(
                name=name,
                topic=ch_info["topic"],
                reason=f"Setup CS Ban System de {interaction.user}"
            )
            created.append(name)
            channel_ids[name] = new_ch.id
            await asyncio.sleep(1.5)  # evita rate limit Discord
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(5)  # asteapta si incearca din nou
                try:
                    new_ch = await category.create_text_channel(name=name, topic=ch_info["topic"])
                    created.append(name)
                    channel_ids[name] = new_ch.id
                except Exception as e2:
                    skipped.append(f"{name} (eroare: {e2})")
            else:
                skipped.append(f"{name} (eroare: {e})")
        except Exception as e:
            skipped.append(f"{name} (eroare: {e})")

    # Trimite panoul in admin-panel
    panel_ch = None
    for ch in category.channels:
        if "admin-panel" in ch.name:
            panel_ch = ch
            break

    if panel_ch:
        embed_panel = discord.Embed(
            title="🎮 CS:GO Admin Panel — BC.LaLeagane.ro",
            description=(
                "Foloseste butoanele de mai jos pentru a gestiona adminii si ban-urile.\n\n"
                "➕ **Adaugă Admin** — completezi SteamID, nume, imunitate, flags\n"
                "🗑️ **Șterge Admin** — introduci SteamID-ul adminului de sters\n"
                "📋 **Listă Admini** — vezi toti adminii activi\n"
                "✅ **Unban** — dezbanezi un jucator dupa SteamID\n"
                "🔍 **Caută Ban-uri** — cauta in istoricul ban-urilor"
            ),
            color=0x5865f2,
            timestamp=datetime.now()
        )
        embed_panel.set_footer(text="BC.LaLeagane.ro | 128 TICK")
        await panel_ch.send(embed=embed_panel, view=ControlPanel())

    # Salveaza ID-urile canalelor in .env (afiseaza pentru user)
    bans_id    = channel_ids.get("🔨・bans", "")
    unbans_id  = channel_ids.get("✅・unbans", "")
    admins_id  = channel_ids.get("👮・admins-log", "")
    panel_id   = channel_ids.get("🎮・admin-panel", "")

    result_embed = discord.Embed(
        title="✅ Setup Complet!",
        color=0x57f287,
        timestamp=datetime.now()
    )

    if created:
        result_embed.add_field(
            name="📁 Canale create",
            value="\n".join(f"✅ {c}" for c in created),
            inline=False
        )
    if skipped:
        result_embed.add_field(
            name="⏭️ Deja existente / sarite",
            value="\n".join(f"⚠️ {s}" for s in skipped),
            inline=False
        )

    result_embed.add_field(
        name="📋 Adauga in .env",
        value=(
            f"```\n"
            f"PANEL_CHANNEL_ID={panel_id}\n"
            f"```\n"
            f"Si pune aceste ID-uri ca webhook-uri in `ban_system.cfg` pe server:\n"
            f"```\n"
            f"bans channel:    {bans_id}\n"
            f"unbans channel:  {unbans_id}\n"
            f"admins channel:  {admins_id}\n"
            f"```"
        ),
        inline=False
    )
    result_embed.set_footer(text="Panoul de control a fost trimis in #admin-panel")
    await interaction.followup.send(embed=result_embed, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_TOKEN nu e setat in .env!")
    else:
        bot.run(TOKEN)
