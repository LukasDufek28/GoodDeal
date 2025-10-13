# Bazos search configuration
# - site: "sk" or "cz"
# - hlokalita: PSC / ZIP (e.g., "040 01"); leave empty "" to search whole country
# - humkreis: radius in km (e.g., "20", "50", "100"); "0" = whole country
# - default_pages: fallback number of pages per search if not specified in each item
# - searches: list of searches with keyword and optional min/max price and pages

CONFIG = {
	"site": "sk",
	"hlokalita": "903 01",  # PSC
	"humkreis": "40",       # okolie in km (radius)
	"default_pages": 3,
	"searches": [
    {
        "keyword": "iphone 11 100%",
        "min_price": 80,
        "max_price": 150
    },
    {
        "keyword": "iphone 12 100%",
        "min_price": 150,
        "max_price": 200
    },
    {
        "keyword": "ps4",
        "min_price": 80,
        "max_price": 180
    },
    {
        "keyword": "playstation 4",
        "min_price": 80,
        "max_price": 180
    },
    {
        "keyword": "nintendo switch",
        "min_price": 120,
        "max_price": 250
    },
    {
        "keyword": "xbox one",
        "min_price": 80,
        "max_price": 160
    }
]
,
}

LISTINGS = []