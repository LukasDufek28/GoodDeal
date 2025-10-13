from typing import Any, Dict

# Application configuration
CONFIG: Dict[str, Any] = {
    # Run once or watch loop
    "watch": False,          # set to True to run forever
    "interval": 5*60,         # seconds between checks in watch mode
    "state_file": None,      # ".bazos_state.json" default state file
    "cities": {
        # "include": [""bratislava"],
        # "exclude": ["trnava"],
    },
    "ignore": [
        "kupim",  # uncomment to ignore "Kúpim / Kúpil by som" etc.
    ],
    "searches": [
        # 🔹 GPUs (always hot & liquid)
        {"keyword": "rtx 3060", "max_price": 150, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 3070", "max_price": 200, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "gtx 1660", "max_price": 90, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rx 6600", "max_price": 120, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rx 6700", "max_price": 170, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 CPUs (good flip with motherboards)
        {"keyword": "ryzen 5 5600", "max_price": 90, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "i5 12400f", "max_price": 100, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Gaming Consoles (quick turnaround)
        {"keyword": "playstation 4", "max_price": 100, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "ps4 slim", "max_price": 110, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "nintendo switch", "max_price": 150, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "xbox one s", "max_price": 100, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Laptops / Office PCs (refurbish & resell)
        {"keyword": "thinkpad", "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "dell latitude", "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "hp elitebook", "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 PC components (steady sales, bundle potential)
        {"keyword": "ssd 1tb", "max_price": 35, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "ddr4 16gb", "max_price": 35, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "b550 motherboard", "max_price": 60, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "z490 motherboard", "max_price": 70, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Peripherals (bundle with PCs)
        {"keyword": "mechanical keyboard", "max_price": 25, "site": "sk", "pages": 1, "include_content": False, "match_in": "title"},
        {"keyword": "gaming monitor 144hz", "max_price": 90, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Smartphones (high liquidity)
        {"keyword": "iphone 11", "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "samsung s20", "max_price": 170, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
    ],
    # GUI review: when True, new listings will be shown in a simple Tkinter review window
    "gui": True,
    # SQLite DB file to store accepted listings
    "db_file": "gooddeal.db",
}
