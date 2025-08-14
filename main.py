import os
import asyncio
import json
from curl_cffi import requests
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from db_manager import init_db, add_dm_user, remove_dm_user, get_all_dm_users, is_dm_user

load_dotenv()
# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.guild_messages = True
from keep_alive import keep_alive

keep_alive()


bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables for tracking
last_results = set()
last_studefi_results = set()
channels = []  # List of channels, one per guild
dm_users = set()  # Will be loaded from database

location_bounds = {
    "lon1": 1.9954155920674,
    "lat1": 49.095452162534826,
    "lon2": 2.7246331213642754,
    "lat2": 48.33343022631068
}

API_URL = "https://trouverunlogement.lescrous.fr/api/fr/search/41"
STUDEFI_URL = "https://www.studefi.fr/main.php"


def get_payload():
    """Generate the API payload with current location bounds"""
    return {
        "idTool":
        41,
        "need_aggregation":
        True,
        "page":
        1,
        "pageSize":
        24,
        "sector":
        None,
        "occupationModes": [],
        "location": [{
            "lon": location_bounds["lon1"],
            "lat": location_bounds["lat1"]
        }, {
            "lon": location_bounds["lon2"],
            "lat": location_bounds["lat2"]
        }],
        "residence":
        None,
        "precision":
        4,
        "equipment": [],
        "price": {
            "max": 10000000
        },
        "area": {
            "min": 0
        },
        "toolMechanism":
        "residual"
    }


def format_rent(rent_info):
    """Format rent information"""
    if rent_info:
        min_rent = rent_info.get('min', 0) / 100  # Convert centimes to euros
        max_rent = rent_info.get('max', 0) / 100
        if min_rent == max_rent:
            return f"{min_rent:.2f}€"
        return f"{min_rent:.2f}€ - {max_rent:.2f}€"
    return "N/A"


def create_accommodation_embed(item):
    """Create a Discord embed for an accommodation"""
    embed = discord.Embed(title=f"🏠 {item.get('label', 'Unknown')}",
                          color=0x00ff00)

    # Basic info
    residence = item.get('residence', {})
    embed.add_field(
        name="📍 Location",
        value=
        f"{residence.get('label', 'Unknown')}\n{residence.get('address', 'N/A')}",
        inline=False)

    # Room details
    area = item.get('area', {})
    area_text = f"{area.get('min', 0)}m²"
    if area.get('max') and area.get('max') != area.get('min'):
        area_text = f"{area.get('min', 0)}-{area.get('max', 0)}m²"

    embed.add_field(
        name="🏠 Room Info",
        value=
        f"**Rooms:** {item.get('roomCount', 'N/A')}\n**Bedrooms:** {item.get('bedroomCount', 'N/A')}\n**Area:** {area_text}",
        inline=True)

    # Rent information
    occupation_modes = item.get('occupationModes', [])
    rent_text = "N/A"
    if occupation_modes:
        rent_info = occupation_modes[0].get('rent', {})
        rent_text = format_rent(rent_info)
        if len(occupation_modes) > 1:
            rent_text += f" ({occupation_modes[0].get('type', 'alone')})"

    embed.add_field(name="💰 Rent", value=rent_text, inline=True)

    # Availability
    available = "✅ Available" if item.get('available',
                                          False) else "❌ Not Available"
    embed.add_field(name="📅 Status", value=available, inline=True)

    # Equipment
    equipments = item.get('equipments', [])
    if equipments:
        equipment_list = [eq.get('label', 'Unknown') for eq in equipments[:5]]
        embed.add_field(name="🛠️ Equipment",
                        value=", ".join(equipment_list),
                        inline=False)

    # Reference
    accommodation_id = item.get('id', 'N/A')
    accommodation_url = f"https://trouverunlogement.lescrous.fr/tools/41/accommodations/{accommodation_id}"
    embed.add_field(
        name="🔗 Reference",
        value=(
            f"Code: {item.get('code', 'N/A')} | Ref: {item.get('reference', 'N/A')}\n"
            f"[Voir sur le site]({accommodation_url})"
        ),
        inline=False
    )

    return embed


def create_studefi_embed(name, link):
    """Create a Discord embed for a Studefi residence"""
    full_link = f"{STUDEFI_URL.split('main.php')[0]}{link}"
    embed = discord.Embed(title=f"🏢 {name}", color=0x00ff00)
    embed.add_field(name="📍 Location", value="Studefi Residence", inline=False)
    embed.add_field(name="🔗 Link", value=f"[View on website]({full_link})", inline=False)
    return embed


async def send_to_all_channels(message=None, embed=None):
    """Send a message or embed to all tracked channels and DM users"""
    # Send to channels
    for ch in channels:
        try:
            if message:
                await ch.send(message)
            if embed:
                await ch.send(embed=embed)
        except Exception as e:
            print(f"Error sending to channel {ch}: {e}")
    
    # Send to DM users
    for user_id in dm_users:
        try:
            user = await bot.fetch_user(user_id)  # Use fetch_user instead of get_user
            if user:
                if message:
                    await user.send(message)
                if embed:
                    await user.send(embed=embed)
        except Exception as e:
            print(f"Error sending DM to user {user_id}: {e}")


async def check_crous_api():
    """Check the CROUS API for new accommodations"""
    global last_results

    if not channels:
        return

    try:
        response = requests.post(API_URL, json=get_payload())
        print(f"Response API code : {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {})
            items = results.get('items', [])
            if items:
                print(items)
            # Create set of current item IDs
            current_results = {item.get('id') for item in items}

            # Find new items
            new_items = [item for item in items if item.get('id') not in last_results]

            # Update last results
            last_results = current_results

            # Send alerts for new items
            if new_items:
                await send_to_all_channels(
                    f"🚨 **{len(new_items)} new accommodation(s) found!**")

                for item in new_items:
                    embed = create_accommodation_embed(item)
                    await send_to_all_channels(embed=embed)

            print(
                f"API check completed. Found {len(items)} total items, {len(new_items)} new."
            )
        else:
            print(f"API request failed with status: {response.status_code}")

    except Exception as e:
        print(f"Error checking API: {e}")


async def check_studefi():
    """Check Studefi website for available residences"""
    global last_studefi_results

    if not channels:
        return

    try:
        response = requests.get(STUDEFI_URL, impersonate="chrome")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            elements = soup.find_all("div", class_="col-sm-6 list-res-elem")
            
            current_results = set()
            new_residences = []

            for elem in elements:
                img_tag = elem.find("img", class_="dispoRes")
                if img_tag:
                    img_src = img_tag.get("src", "")
                    if "non_disponibles" not in img_src:
                        name_tag = elem.find("div", class_="list-res-link").find("a")
                        name = name_tag.get_text(strip=True)
                        link = name_tag.get("href", "")
                        result_id = f"{name}:{link}"
                        current_results.add(result_id)
                        
                        if result_id not in last_studefi_results:
                            new_residences.append((name, link))

            last_studefi_results = current_results

            if new_residences:
                await send_to_all_channels(
                    f"🏢 **{len(new_residences)} new Studefi residence(s) available!**")
                for name, link in new_residences:
                    embed = create_studefi_embed(name, link)
                    await send_to_all_channels(embed=embed)

    except Exception as e:
        print(f"Error checking Studefi: {e}")


@tasks.loop(seconds=3)
async def api_monitor():
    """Task that runs every 5 seconds to check the API"""
    await check_crous_api()


@tasks.loop(seconds=3)
async def studefi_monitor():
    """Task that runs every 5 seconds to check Studefi"""
    await check_studefi()


@api_monitor.before_loop
@studefi_monitor.before_loop
async def before_api_monitor():
    """Wait until the bot is ready before starting the monitoring"""
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    global channels, dm_users
    print(f'Bot logged in as {bot.user}')
    
    # Initialize database and load DM users
    init_db()
    dm_users = get_all_dm_users()
    print(f"Loaded {len(dm_users)} DM users from database")

    channels = []
    # Find or create CrousAlert channel
    for guild in bot.guilds:
        existing_channel = discord.utils.get(guild.channels, name='crousalert')
        if existing_channel:
            channels.append(existing_channel)
        else:
            # Create the channel
            try:
                channel = await guild.create_text_channel('crousalert')
                await channel.send(
                    "🏠 **CROUS Alert Bot Started!**\nMonitoring for new accommodations every 5 seconds."
                )
                channels.append(channel)
            except discord.Forbidden:
                print(f"No permission to create channel in {guild.name}")

    if channels:
        print(f"Using channels: {[ch.name for ch in channels]}")
        # Start both monitoring tasks
        if not api_monitor.is_running():
            api_monitor.start()
        if not studefi_monitor.is_running():
            studefi_monitor.start()
    else:
        print("No suitable channel found or created")


@bot.command(name='setlocation')
async def set_location(ctx, lon1: float, lat1: float, lon2: float,
                       lat2: float):
    """Set custom location boundaries for the search
    Usage: !setlocation <lon1> <lat1> <lon2> <lat2>
    Example: !setlocation 1.99 49.09 2.72 48.33
    """
    global location_bounds

    location_bounds = {"lon1": lon1, "lat1": lat1, "lon2": lon2, "lat2": lat2}

    embed = discord.Embed(
        title="📍 Location Updated",
        description="Search area has been updated with new coordinates:",
        color=0x0099ff)
    embed.add_field(name="Coordinates",
                    value=f"Point 1: {lon1}, {lat1}\nPoint 2: {lon2}, {lat2}",
                    inline=False)

    await ctx.send(embed=embed)
    print(f"Location bounds updated: {location_bounds}")


@bot.command(name='status')
async def status(ctx):
    """Show current bot status and configuration"""
    embed = discord.Embed(title="🤖 Bot Status", color=0x0099ff)

    # Search Area Info
    embed.add_field(
        name="📍 Current Search Area",
        value=f"Point 1: {location_bounds['lon1']}, {location_bounds['lat1']}\n"
        f"Point 2: {location_bounds['lon2']}, {location_bounds['lat2']}",
        inline=False)

    # Monitoring Status
    crous_status = "✅ Active" if api_monitor.is_running() else "❌ Inactive"
    studefi_status = "✅ Active" if studefi_monitor.is_running() else "❌ Inactive"
    
    embed.add_field(
        name="🔄 Monitoring Status",
        value=f"**CROUS:** {crous_status}\n**Studefi:** {studefi_status}\n"
              f"*Checking every 5 seconds*",
        inline=False
    )

    # Statistics
    embed.add_field(
        name="📊 Currently Tracking",
        value=f"**CROUS:** {len(last_results)} accommodations\n"
              f"**Studefi:** {len(last_studefi_results)} residences",
        inline=False
    )

    # Service URLs
    embed.add_field(
        name="🔗 Service URLs",
        value=f"[CROUS]({API_URL.split('/api')[0]})\n"
              f"[Studefi]({STUDEFI_URL})",
        inline=False
    )

    # DM Notifications Status
    embed.add_field(
        name="📱 DM Notifications",
        value=f"Active for {len(dm_users)} users\n"
              f"Your status: {'✅ Enabled' if ctx.author.id in dm_users else '❌ Disabled'}",
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command(name='test')
async def test(ctx):
    """Test the API connection and show current results"""
    await ctx.send("🔍 Testing API connection...")

    try:
        response = requests.post(API_URL, json=get_payload())

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {})
            items = results.get('items', [])
            total = results.get('total', {}).get('value', 0)

            embed = discord.Embed(
                title="✅ API Test Successful",
                description=
                f"Found {total} total accommodations\nShowing first result:",
                color=0x00ff00)

            if items:
                # Show first item as example
                first_item = items[0]
                embed.add_field(
                    name="Example Result",
                    value=f"**{first_item.get('label', 'Unknown')}**\n"
                    f"Location: {first_item.get('residence', {}).get('label', 'Unknown')}\n"
                    f"Available: {'Yes' if first_item.get('available') else 'No'}",
                    inline=False)

            await ctx.send(embed=embed)
        else:
            await ctx.send(
                f"❌ API test failed with status: {response.status_code}")
    except Exception as e:
        await ctx.send(f"❌ API test failed: {str(e)}")


@bot.command(name='dm')
async def toggle_dm(ctx):
    """Toggle DM notifications for the user"""
    user_id = ctx.author.id
    
    if user_id in dm_users:
        dm_users.remove(user_id)
        remove_dm_user(user_id)
        embed = discord.Embed(
            title="📳 DM Notifications Disabled",
            description="You will no longer receive notifications in DM",
            color=0xff0000
        )
    else:
        dm_users.add(user_id)
        add_dm_user(user_id)
        embed = discord.Embed(
            title="📳 DM Notifications Enabled",
            description="You will now receive notifications in DM",
            color=0x00ff00
        )
    
    await ctx.send(embed=embed)


@bot.command(name='help_crous')
async def help_crous(ctx):
    """Show help information for the CROUS bot"""
    embed = discord.Embed(
        title="🏠 CROUS Alert Bot Help",
        description="This bot monitors CROUS housing for new accommodations",
        color=0x0099ff)

    embed.add_field(
        name="Commands",
        value=
        "**!setlocation** `<lon1> <lat1> <lon2> <lat2>` - Set search area\n"
        "**!status** - Show bot status\n"
        "**!test** - Test API connection\n"
        "**!dm** - Toggle DM notifications\n"
        "**!help_crous** - Show this help",
        inline=False)

    embed.add_field(name="How it works",
                    value="• Bot checks API every 5 seconds\n"
                    "• Alerts when new accommodations appear\n"
                    "• Location boundaries are customizable\n"
                    "• Shows detailed accommodation info",
                    inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def ping(ctx):
    print("Ping command received")
    await ctx.send("Pong!")


# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Missing required argument. Use `!help_crous` for command usage."
        )
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Command error: {error}")


# Run the bot
if __name__ == "__main__":
    try:
        token = os.getenv("TOKEN", "")
        if token == "":
            raise Exception(
                "Please add your Discord bot token to the TOKEN environment variable."
            )
        bot.run(token)
    except discord.HTTPException as e:
        if e.status == 429:
            print(
                "The Discord servers denied the connection for making too many requests"
            )
            print(
                "Get help from https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests"
            )
        else:
            raise e
