import discord, predict, requests, geopy
from datetime import datetime
from geopy.geocoders import Nominatim

TOKEN = open("./satellite_prediction_bot_secret.txt").read()

client = discord.Client()

TLE_UPDATE_URL = "https://www.celestrak.com/NORAD/elements/active.txt"
TLE_FILE = "./active.txt"
TLE_LAST_UPDATED = 0
GEOLOCATOR = Nominatim(user_agent="Satellite Prediction Bot")

HELP_MSG = {
    "title": "Usage: !predict \"<sat>\" <loc>|\"<place>\" <num> [-u] [-h]",
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
            "value": "number of passes to predict"
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
    ]
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
def parse_args(command):
    command = command.replace("'", '"').split("\"")
    sat_name = command[1].strip()
    if len(command) > 3:
        place = command[3].strip()
        location = GEOLOCATOR.geocode(place)
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        pass_count = command[4].strip()
    else:
        command = "".join(command[2:]).split(")")
        pass_count = command[1].strip()
        lat_lon = command[0].split("(")[1].split(",")
        lat = lat_lon[0].strip()
        lon = lat_lon[1].strip()
        alt = lat_lon[2].strip()

    print(sat_name)
    print(lat)
    print(lon)
    print(alt)
    print(pass_count)

    return sat_name, (int(lat), int(lon)*-1, int(alt)), int(pass_count)

@client.event
async def on_ready():
    print('logged in to Discord as {} {}\n'.format(client.user.name, client.user.id))


@client.event
async def on_message(message):
    if message.content.startswith("!predict"):
        command = message.content[9:]

        #handle closing the bot
        if command == "close":
            await message.channel.send("Exiting...")
            await client.close()
            exit()

        #handle updating the tle
        elif "-u" in command:
            update_tle()
            command.replace("-u", "")
            await message.channel.send("TLE updated")

        if "-h" in command:
            command.replace("-h", "")
            await message.channel.send(embed=discord.Embed.from_dict(HELP_MSG))

        #handle prediction commands
        print(command.strip())
        if len(command.strip()) > 0:
            #update the tle if it hasn't been updated in 12 hours
            if TLE_LAST_UPDATED == 0 or datetime.now().timestamp() - TLE_LAST_UPDATED > 43200:
                update_tle()
                await message.channel.send("TLE updated")

            #get command arguments
            sat_name, loc, pass_count = parse_args(command)

            #find the tle for the specifed sat in the tle file
            tle = find_sat_in_tle(sat_name, TLE_FILE)

            #predict the passes and add them to a list
            p = predict.transits(tle, loc)
            passes = []
            for i in range(pass_count):
                transit = next(p)
                while transit.peak()["elevation"] < 20:
                    transit = next(p)

                passes.append({
                    "satellite": sat_name,
                    "start": round(transit.start),
                    "end": round(transit.end),
                    "peak_elevation": round(transit.peak()['elevation'], 1),
                    "duration": round(transit.duration()),
                    "azimuth": round(transit.at(transit.start)['azimuth'], 1)
                })

            #respond with an embeded message
            response = discord.Embed(title=sat_name + " Passes")
            for ps in passes:
                response.add_field(
                    name=datetime.utcfromtimestamp(ps['start']).strftime("%B %-d, %Y at %-H:%M:%S UTC"), 
                    value="Peak Elevation: {}\nDuration: {}\nAzimuth: {}\nEnd: {}".format(ps['peak_elevation'], ps['duration'], ps['azimuth'], datetime.utcfromtimestamp(ps['end']).strftime("%B %-d, %Y at %-H:%M:%S UTC")),
                    inline=False
                    )
            await message.channel.send(embed=response)
            

client.run(TOKEN)