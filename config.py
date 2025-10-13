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
        "nefunkcny",
        "poskodeny",
        "pokazeny",
        "rozbity",
    ],
    "searches": [
        # 🔹 GPUs (tight caps = quick profit)
        {"keyword": "rtx 4090",      "min_price": 700, "max_price": 1500, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 4080",      "min_price": 500, "max_price": 900,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 4070 ti",   "min_price": 250, "max_price": 500,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 4070",      "min_price": 200, "max_price": 420,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 4060 ti",   "min_price": 150, "max_price": 250,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 3080",      "min_price": 200, "max_price": 350,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 3070",      "min_price": 150, "max_price": 220,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "rtx 3060 ti",   "min_price": 130, "max_price": 180,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Game consoles (very liquid)
        {"keyword": "ps5",                   "min_price": 180, "max_price": 300, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "playstation 5",         "min_price": 180, "max_price": 300, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "xbox series x",         "min_price": 150, "max_price": 250, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "xbox series s",         "min_price": 80,  "max_price": 150, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "nintendo switch oled",  "min_price": 120, "max_price": 180, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "nintendo switch",       "min_price": 90,  "max_price": 140, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        # {"keyword": "steam deck",            "min_price": 160, "max_price": 250, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},

        # 🔹 VR / handhelds
        # {"keyword": "meta quest 2",  "min_price": 80,  "max_price": 140, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "meta quest 3",  "min_price": 180, "max_price": 250, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 iPhones (top liquidity)
        {"keyword": "iphone 14 pro", "min_price": 400, "max_price": 600, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "iphone 14 256",     "min_price": 280, "max_price": 400, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "iphone 13 pro", "min_price": 320, "max_price": 450, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "iphone 13 256",     "min_price": 220, "max_price": 300, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "iphone 12",     "min_price": 150, "max_price": 220, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},
        {"keyword": "iphone 11 128",     "min_price": 100, "max_price": 150, "site": "sk", "pages": 3, "include_content": False, "match_in": "title"},

        # 🔹 Apple gear (moves fast)
        # {"keyword": "macbook air m1",  "min_price": 250, "max_price": 400, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "macbook pro m1",  "min_price": 350, "max_price": 550, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "ipad pro 11",     "min_price": 180, "max_price": 300, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "ipad air",        "min_price": 90,  "max_price": 150, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "airpods pro 2",   "min_price": 70,  "max_price": 120, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        {"keyword": "airpods 3",       "min_price": 50,  "max_price": 80,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "apple watch series 8", "min_price": 120, "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "apple watch series 7", "min_price": 100, "max_price": 150, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 CPUs (only very liquid SKUs)
        # {"keyword": "ryzen 5 5600x", "min_price": 60,  "max_price": 90,  "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "ryzen 7 5800x", "min_price": 90,  "max_price": 130, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "i7 12700k",     "min_price": 120, "max_price": 180, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Storage (cheap, volume, quick sell)
        # {"keyword": "nvme 1tb", "min_price": 15, "max_price": 25, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},
        # {"keyword": "nvme 2tb", "min_price": 30, "max_price": 50, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

        # 🔹 Monitors / accessories (only highly demanded specs)
        # {"keyword": "144hz monitor", "min_price": 60, "max_price": 100, "site": "sk", "pages": 2, "include_content": False, "match_in": "title"},

    ],
    # GUI review: when True, new listings will be shown in a simple Tkinter review window
    "gui": True,
    # SQLite DB file to store accepted listings
    "db_file": "gooddeal.db",
}
