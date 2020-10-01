import discord, predict, requests, geopy, difflib, pytz
from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

TOKEN = open("./satellite_prediction_bot_secret.txt").read()

client = discord.Client()

TLE_UPDATE_URL = "https://www.celestrak.com/NORAD/elements/active.txt"
TLE_FILE = "./active.txt"
TLE_LAST_UPDATED = 0
GEOLOCATOR = Nominatim(user_agent="Satellite Prediction Bot")

HELP_MSG = {
    "title": "Usage: !predict \"<sat>\" <loc>|\"<place>\" [<num>] [-u] [-h]",
    "description": "where:",
    "fields": [
        {
            "name": "<sat>",
            "value": "the name of the satellite"
        },
        {
            "name": "<loc>",
            "value": "formatted (<lat>,<lon>,<alt>) information"
        },
        {
            "name": "<place>",
            "value": "a location search term"
        },
        {
            "name": "<num>",
            "value": "number of passes to predict (default: 1)"
        },
        {
            "name": "-u",
            "value": "manually update TLE"
        },
        {
            "name": "-h",
            "value": "show usage and command information"
        },
        {
            "name": "Examples:",
            "value": "!predict \"NOAA 19\" (49,-123,20) 2\n !predict \"ISS (ZARYA)\" \"vancouver, canada\" 10"
        }
    ],
    "footer" : {
        "text": "Ping or message @Blobtoe with any concerns."
    }
}




#find the tle for a specific sat in the tle file
def find_sat_in_tle(sat_name, tle_file):
    tle_lines = open(tle_file).read()
    index = tle_lines.index(sat_name)
    tle = tle_lines[index:index+165]
    return tle

#update tle from web
def update_tle():
    global TLE_LAST_UPDATED
    r = requests.get(TLE_UPDATE_URL)
    open(TLE_FILE, "wb").write(r.content)
    TLE_LAST_UPDATED = datetime.now().timestamp()

#parse arguments from command
#this is digusting
def parse_args(command):
    command = command.replace("'", '"').split("\"")
    sat_name = command[1].strip()
    if len(command) > 3:
        place = command[3].strip()
        location = GEOLOCATOR.geocode(place)
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        if command[4]:
            pass_count = command[4].strip()
        else:
            pass_count = 1
    else:
        command = "".join(command[2:]).split(")")
        lat_lon = command[0].split("(")[1].split(",")
        lat = lat_lon[0].strip()
        lon = lat_lon[1].strip()
        alt = lat_lon[2].strip()
        if command[1]:
            pass_count = command[1].strip()
        else:
            pass_count = 1

    return sat_name, (int(lat), int(lon), int(alt)), int(pass_count)

@client.event
async def on_ready():
    print('logged in to Discord as {} {}\n'.format(client.user.name, client.user.id))
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!predict -h"))


@client.event
async def on_message(message):
    if message.content.startswith("!predict"):
        command = message.content[9:]

        if "-u" in command:
            update_tle()
            command.replace("-u", "")
            await message.channel.send("TLE updated")

        if "-h" in command:
            command.replace("-h", "")
            await message.channel.send(embed=discord.Embed.from_dict(HELP_MSG))


        #handle prediction commands
        if len(command.strip()) > 0:
            #update the tle if it hasn't been updated in 12 hours
            if TLE_LAST_UPDATED == 0 or datetime.now().timestamp() - TLE_LAST_UPDATED > 43200:
                update_tle()
                await message.channel.send("TLE updated")

            #get command arguments
            sat_name, loc, pass_count = parse_args(command)

            names = [name.strip() for name in open(TLE_FILE).read().split("\n")[0::3]]
            matches = difflib.get_close_matches(sat_name.upper(), names)
            if len(matches) == 0:
                await message.channel.send("Error: Failed to find satellite")
                return
            sat_name = matches[0]

            #find the tle for the specifed sat in the tle file
            tle = find_sat_in_tle(sat_name, TLE_FILE)

            tf = TimezoneFinder()
            tz = tf.timezone_at(lat=loc[0], lng=loc[1])
            utc_offset = datetime.now(pytz.timezone(tz)).strftime("%z")

            #predict the passes and add them to a list
            p = predict.transits(tle, (loc[0], loc[1]*-1, loc[2]))
            passes = []
            for i in range(pass_count):
                transit = next(p)

                #while transit.peak()["elevation"] < 20:
                #    transit = next(p)

                passes.append({
                    "satellite": sat_name,
                    "start": round(transit.start),
                    "end": round(transit.end),
                    "peak_elevation": round(transit.peak()['elevation'], 1),
                    "duration": round(transit.duration()),
                    "azimuth": round(transit.at(transit.start)['azimuth'], 1)
                })

            #respond with an embeded message
            response = discord.Embed(title=sat_name + " passes over {} [UTC{}]".format(str(loc), utc_offset))
            for ps in passes:
                delta = datetime.utcfromtimestamp(ps['start']) - datetime.utcnow()
                hours, minutes = divmod(delta.seconds/60, 60)
                response.add_field(
                    name=datetime.utcfromtimestamp(ps['start']).strftime("%B %-d, %Y at %-H:%M:%S UTC") + " (in {} hours and {} minutes)".format(round(hours), round(minutes)), 
                    value="Peak Elevation: {}\nDuration: {}\nAzimuth: {}\nEnd: {}".format(ps['peak_elevation'], ps['duration'], ps['azimuth'], datetime.utcfromtimestamp(ps['end']).strftime("%B %-d, %Y at %-H:%M:%S UTC")),
                    inline=False
                    )
            await message.channel.send(embed=response)
            

client.run(TOKEN)