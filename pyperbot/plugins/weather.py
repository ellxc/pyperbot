from pyperbot.wrappers import plugin, command
import json
import async_timeout
import aiohttp
directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N']


@plugin
class Weather:

    @command(rate_limit_no=2)
    async def weather(self, message):
        """Get the current weather using the https://darksky.net API.
        """
        if not message.text:
            geop = await self.geopip(message.domain)
            long = geop['longitude']
            lat = geop['latitude']
            name = "{}, {}, {}, {}".format(geop['zip_code'], geop['city'], geop['region_name'], geop['country_name'])
        else:
            mapbox = await self.mapbox(message.text)
            long, lat = mapbox['center']
            name = mapbox['place_name']

        w = await self.get_forecast_io_weather(lat, long)
        current = w['currently']
        place = "Weather for {}:".format(name)
        summary = (w.get('minutely', {}).get('summary', '').replace('.', '') or current['summary']) + "."
        precip = "{:.0f}% chance of {}.".format(current['precipProbability']*100, current.get('precipType', 'rain'))
        temp = "{}°C, feels like {}°C.".format(current['temperature'], current['apparentTemperature'])
        humid = "{:0.0f}% humidity.".format(current['humidity']*100)
        winds = "{}mph winds going {}.".format(current['windSpeed'],
                                               directions[int((current['windBearing']+11.25) / 22/5)])

        r = " ".join((place, summary, precip, temp, humid, winds))
        return message.reply(data=w, text=r)

    async def geopip(self, lookup):
        url = "http://freegeoip.net/json/" + lookup
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                j = json.loads(text)
        return j

    async def mapbox(self, place):
        # Use Yahoo's yql to build the query
        if not place:
            raise Exception("You must provide a place name.")

        if 'mapbox' not in self.bot.apikeys or not self.bot.apikeys['mapbox']:
            raise Exception("No mapbox api key found, please contact administrator")
        key = self.bot.apikeys['mapbox']

        url = f'https://api.mapbox.com/geocoding/v5/mapbox.places/{place}.json?type=poi&access_token={key}'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                j = json.loads(text)

        first = j['features'][0]
        return first

    async def get_forecast_io_weather(self, lat, long):

        if 'darksky' not in self.bot.apikeys or not self.bot.apikeys['darksky']:
            raise Exception("No darksky api key found, please contact administrator")
        key = self.bot.apikeys['darksky']

        # Build a darksky request string.
        url = "https://api.darksky.net/forecast/{}/{},{}?units=uk2".format(key, lat, long)

        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    try:
                        return await resp.json()
                    except Exception:
                        raise Exception(await resp.text())
