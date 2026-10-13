"""Meloghrano Cafe (Basavanagudi, Bengaluru) - demo data.

Source: the café's menu images on Zomato
(zomato.com/bangalore/meloghrano-cafe-basavanagudi-bangalore/menu),
transcribed October 2026. Zomato hosts several menu versions with differing
prices; this uses the newer cream-design menu as the primary source and adds
only non-overlapping items from the printed "Special Menu" pages. Items shown
without a price were omitted. Spelling was normalised (e.g. "panner" ->
"Paneer"); prices were not changed.

Conventions (see data.py): dietary/allergen data is NOT verified by the café.
Only items the menu itself shows contain egg are marked non-vegetarian;
everything else is "unknown". Strength and sweetness are coarse estimates from
the drink type (used for ranking), not restaurant claims. No dish photos are
used - the UI shows neutral placeholders.
"""

import re
from decimal import Decimal as D

from app.seed.data import item

# ---- add-ons --------------------------------------------------------------

def _addon(name, price, group):
    return dict(name=name, group_name=group, price=D(price), allergens=None)


ADDONS = [
    # coffee
    *[_addon(n, "40", "Flavour enhancers") for n in
      ("Caramel", "Sea Salt Caramel", "Hazelnut", "Vanilla", "Almond Praline", "Apple Pie", "Salted Pistachio")],
    _addon("Oat Milk", "69", "Vegan milk"), _addon("Soy Milk", "69", "Vegan milk"),
    _addon("Coconut Milk", "70", "Vegan milk"), _addon("Almond Milk", "70", "Vegan milk"),
    *[_addon(n, "50", "Chocolate") for n in ("Dark Chocolate", "Milk Chocolate", "White Chocolate")],
    _addon("Whipped Cream", "40", "Toppings"),
    # breakfast
    *[_addon(n, "100", "Breakfast add-ons") for n in
      ("Bread Toast", "Hash Brown", "Baked Beans", "Choice of Egg", "Mushroom Crisps", "Mashed Potato")],
    _addon("Fresh Mozzarella (breakfast)", "120", "Breakfast add-ons"),
    # salads & wraps
    *[_addon(n, "60", "Veggies & extras") for n in
      ("Tomato", "Bell Pepper", "English Cucumber", "Egg", "Onion", "Zucchini", "Broccoli")],
    _addon("Feta Cheese", "90", "Cheese"), _addon("Fresh Mozzarella", "90", "Cheese"), _addon("Parmesan", "90", "Cheese"),
    # snacks
    _addon("Peri Peri (fries)", "50", "Fries add-ons"), _addon("Cheese (fries)", "60", "Fries add-ons"),
    *[_addon(n, "89", "Dips") for n in ("Garlic Aioli", "Classic Cheese Dip", "Roasted Bell Pepper Dip", "Pesto Dip")],
    # desserts
    *[_addon(n, "30", "Sundae add-ons") for n in ("Roasted Cashew", "Roasted Almonds", "Roasted Peanuts")],
    _addon("Fudge Sauce", "40", "Sundae add-ons"), _addon("Fresh Chocolate Sauce", "60", "Sundae add-ons"),
    _addon("Ice Magic Sauce", "50", "Sundae add-ons"),
]

COFFEE_EXTRAS = ["Caramel", "Sea Salt Caramel", "Hazelnut", "Vanilla", "Almond Praline", "Apple Pie",
                 "Salted Pistachio", "Oat Milk", "Soy Milk", "Coconut Milk", "Almond Milk"]
BLACK_EXTRAS = ["Caramel", "Sea Salt Caramel", "Hazelnut", "Vanilla"]
MATCHA_EXTRAS = ["Oat Milk", "Soy Milk", "Coconut Milk", "Almond Milk"]
BREAKFAST_EXTRAS = ["Bread Toast", "Hash Brown", "Baked Beans", "Choice of Egg", "Mushroom Crisps", "Mashed Potato",
                    "Fresh Mozzarella (breakfast)"]
SALAD_EXTRAS = ["Tomato", "Bell Pepper", "English Cucumber", "Egg", "Onion", "Feta Cheese", "Fresh Mozzarella", "Parmesan"]
WRAP_EXTRAS = ["Tomato", "Bell Pepper", "Zucchini", "Broccoli", "Onion", "Fresh Mozzarella"]
DIPS = ["Garlic Aioli", "Classic Cheese Dip", "Roasted Bell Pepper Dip", "Pesto Dip"]
SUNDAE_EXTRAS = ["Roasted Cashew", "Roasted Almonds", "Roasted Peanuts", "Fudge Sauce", "Fresh Chocolate Sauce",
                 "Ice Magic Sauce"]

PASTA_CHOICE = [("Penne", None), ("Fusilli", None), ("Spaghetti", None), ("Fettuccine", None)]

# ---- helpers ---------------------------------------------------------------

FLAVOUR_WORDS = [
    "chocolate", "caramel", "hazelnut", "vanilla", "cinnamon", "berry", "strawberry", "mango", "coconut",
    "orange", "lemon", "pistachio", "peanut", "biscoff", "nutella", "chilli", "cheese", "mushroom", "pesto",
    "truffle", "garlic", "tomato", "creamy", "rose", "ginger", "litchi", "cranberry", "guava", "pineapple",
    "mint", "honey", "matcha", "cocoa", "burrata", "basil", "nutty", "spicy", "avocado", "paneer", "spiced",
]
EGG_RE = re.compile(r"\begg|\bomelette|contains egg", re.I)


def _flavours(name, desc):
    text = f"{name} {desc or ''}".lower()
    tags = [w for w in FLAVOUR_WORDS if w in text]
    if "nut" in text.split() or "nuts" in text or "walnut" in text:
        tags.append("nutty")
    return list(dict.fromkeys(tags))[:6]


def M(name, price, desc=None, *, variants=None, egg=None, **kw):
    """One menu item. ``variants``: [(label, price or None=same price)]."""
    if egg is None:
        egg = bool(EGG_RE.search(f"{name} {desc or ''}"))
    if egg:
        kw.setdefault("veg", False)
        kw.setdefault("vegan", False)
    kw.setdefault("flavors", _flavours(name, desc))
    if variants:
        kw["variants"] = [(label, p or price, i == 0) for i, (label, p) in enumerate(variants)]
        kw.setdefault("variant_required", True)
    return dict(_name=name, _price=price, _desc=desc, **kw)


def category(name, slug, description, defaults, items):
    built = []
    for raw in items:
        spec = {**defaults, **{k: v for k, v in raw.items() if not k.startswith("_")}}
        built.append(item(raw["_name"], raw["_price"], desc=raw["_desc"], **spec))
    return dict(name=name, slug=slug, description=description, items=built)


HOT_COFFEE = dict(type="beverage", temp="hot", coffee=True, tags=["coffee", "espresso"],
                  pairs=["chocolate", "creamy", "nutty", "caramel", "biscoff", "nutella"])
COLD_COFFEE = dict(type="beverage", temp="cold", coffee=True, tags=["coffee"],
                   pairs=["chocolate", "creamy", "nutty", "cheese"])
TEA = dict(type="beverage", temp="hot", coffee=False, tags=["tea"], pairs=["cheese", "spiced", "honey"])
COLD_NON_COFFEE = dict(type="beverage", temp="cold", coffee=False, pairs=["cheese", "spicy", "garlic"])
FOOD = dict(type="food", coffee=False, pairs=["mint", "lemon", "orange", "cranberry"])
DESSERT = dict(type="dessert", coffee=False, pairs=["coffee", "espresso", "cocoa"])

# ---- menu ------------------------------------------------------------------

CATEGORIES = [
    category("Classic Hot Coffees", "classic-hot-coffees", "Espresso classics.", HOT_COFFEE, [
        M("Espresso", "160", "A concentrated shot of our finest beans, rich in crema and deep in flavor.", strength=5, sweet=1, addons=BLACK_EXTRAS),
        M("Nucleus Paragon Espresso", "180", "A refined espresso experience, extracted with precision using Nucleus Paragon technology - crisp, vibrant, and ultra-clean.", strength=5, sweet=1),
        M("Americano", "180", "Espresso softened with hot water for a smooth, easy-drinking coffee with gentle acidity and a bold aroma.", strength=4, sweet=1, addons=BLACK_EXTRAS),
        M("Cortado", "180", "Equal parts espresso and steamed milk - a compact, creamy coffee with a delicate balance of strength and softness.", strength=4, sweet=1, addons=COFFEE_EXTRAS),
        M("Macchiato", "180", "A bold espresso \"marked\" with a touch of milk foam. Short, intense, and layered with flavour.", strength=4, sweet=1, addons=COFFEE_EXTRAS),
        M("Cappuccino", "220", "Espresso, steamed milk, and airy foam in perfect harmony. Light, silky, and comforting.", strength=3, sweet=1, featured=True, addons=COFFEE_EXTRAS),
        M("Latte", "230", "Smooth espresso combined with creamy steamed milk. Mellow and full-bodied.", strength=2, sweet=1, addons=COFFEE_EXTRAS),
        M("Flat White", "220", "A velvety-rich coffee with micro-foamed milk and double espresso. Smooth, strong, and satisfying.", strength=4, sweet=1, addons=COFFEE_EXTRAS),
        M("Bombon", "220", "A Spanish treat. Espresso poured over sweetened condensed milk - rich, indulgent, and deeply comforting.", strength=3, sweet=5),
        M("Mocha", "260", "Espresso blended with dark chocolate and steamed milk - a luscious treat.", strength=3, sweet=4,
          addons=["Dark Chocolate", "Milk Chocolate", "White Chocolate"] + COFFEE_EXTRAS),
    ]),
    category("Signature Flavoured Lattes", "signature-lattes", "Hot lattes with natural infusions.", {**HOT_COFFEE, "sweet": 4, "strength": 2}, [
        M("Ginger Spice Latte", "260", "Infused with warm gingerbread and aromatic cinnamon - spicy, nostalgic, and soul-soothing.", addons=MATCHA_EXTRAS),
        M("Gulkhan Latte", "260", "A fragrant fusion of rose petals and velvety vanilla - delicate, floral, and creamy.", addons=MATCHA_EXTRAS),
        M("Honey Spice Latte", "250", "Pure honey and warming cinnamon in a sweet, spiced latte - earthy and naturally balanced.", addons=MATCHA_EXTRAS),
    ]),
    category("Rockline Specials", "rockline-specials", "Elevated, indulgent lattes with signature ingredients.", {**HOT_COFFEE, "sweet": 4, "strength": 2, "temp": None}, [
        M("Biscoff Latte", "270", "Espresso with velvety steamed milk and creamy Biscoff cookie butter. Warm, spiced, and biscuit-smooth.", featured=True),
        M("Caramel Macchiato", "280", "Rich espresso layered over vanilla milk and topped with golden caramel. Balanced sweetness with bold depth."),
        M("Tiramisu Latte", "350", "A dessert-in-a-cup inspired by the Italian classic. Espresso, cocoa, mascarpone flavour, and a dusting of cocoa - smooth, creamy, and indulgent."),
        M("Pistachio Latte", "280", "Nutty, subtly sweet pistachio blended into a smooth latte. Earthy and creamy with a natural richness."),
        M("Nutella Latte", "265", "A velvety fusion of espresso and luscious Nutella. Smooth, chocolatey, and satisfyingly indulgent."),
        M("Peanut Latte", "270", "A roasted peanut twist on the classic latte - warm, bold, and irresistibly nutty."),
    ]),
    category("Classic Iced Coffees", "classic-iced-coffees", "Freshly brewed over ice.", COLD_COFFEE, [
        M("Iced Espresso", "160", "A chilled, concentrated shot of espresso poured over ice. Crisp, sharp, and invigorating.", strength=5, sweet=1, tags=["coffee", "espresso"]),
        M("Iced Americano", "180", "Smooth espresso diluted with cold water and poured over ice. Light-bodied and easy to sip with a bold undertone.", strength=4, sweet=1, tags=["coffee", "espresso"], addons=BLACK_EXTRAS),
        M("Iced Latte", "230", "Espresso over chilled milk with ice - creamy, mild, and perfect for a relaxed, refreshing drink.", strength=2, sweet=1, tags=["coffee", "espresso"], addons=COFFEE_EXTRAS),
        M("Flavoured Iced Latte", "250", "Your classic iced latte elevated with rich, natural flavours - a touch of indulgence in every sip.", strength=2, sweet=4,
          variants=[("Vanilla", None), ("Hazelnut", None), ("Caramel", None)], addons=MATCHA_EXTRAS),
        M("Iced Mocha", "250", "Dark chocolate meets espresso and milk over ice. A bold, chocolaty refreshment for any time of day.", strength=3, sweet=4, addons=MATCHA_EXTRAS),
        M("Vietnamese Shekarato", "250", "Cinnamon, condensed milk, and espresso shaken over ice for a creamy, spiced twist on cold coffee.", strength=4, sweet=4, featured=True),
        M("Espresso Martini", "250", "A non-alcoholic twist on a classic. Chilled espresso shaken with vanilla and a splash of lemon - bold, aromatic, and sophisticated.", strength=4, sweet=2,
          variants=[("Vanilla", None), ("Lemon", None)]),
        M("Choco Burst", "250", "Espresso, caramel and chocolate - decadent and indulgent, poured over ice. Dessert meets coffee.", strength=3, sweet=5),
        M("Popnut Latte", "250", "A tropical twist on cold brew with coconut. Notes of roasted coffee meet creamy coconut for a nutty, smooth, and refreshing experience.", strength=3, sweet=3),
    ]),
    category("Cold Brews", "cold-brews", "Brewed low and slow for 18+ hours. Naturally smooth and low in acidity.", {**COLD_COFFEE, "tags": ["coffee", "cold brew"]}, [
        M("Classic Cold Brew", "200", "Mellow and bold with notes of cocoa and toasted nuts - the perfect refreshment for any time of day.", strength=4, sweet=1, featured=True),
        M("Tropical Cold Brew", "230", "Cold brew with a fruity twist. Choose your infusion for a zesty, juicy refreshment with subtle coffee depth.", strength=3, sweet=2,
          variants=[("Orange", None), ("Cranberry", None), ("Apple", None), ("Pineapple", None)]),
        M("Cold Brew Latte", "200", "Silky cold brew blended with chilled milk - balanced, bold, and creamy.", strength=3, sweet=1),
        M("Flavoured Cold Brew Latte", "220", "A richer take on our latte, enhanced with natural flavors. Smooth, sweet, and indulgent.", strength=3, sweet=4,
          variants=[("Vanilla", None), ("Hazelnut", None), ("Caramel", None)]),
    ]),
    category("Sparkling & Probiotic Coffee", "sparkling-coffee", "Espresso or cold brew with tonic, ginger ale or natural fermentation.", {**COLD_COFFEE, "strength": 3, "sweet": 2}, [
        M("Espresso Tonic", "240", "A refreshing balance of rich espresso and bubbly tonic water. Light, bright, and bittersweet."),
        M("Flavoured Espresso Tonic", "260", "The signature espresso tonic with your choice of vibrant natural fruit infusions.", variants=[(f, None) for f in ("Orange", "Litchi", "Cranberry", "Yuzu", "Peach", "Kiwi")]),
        M("Cold Brew Tonic", "260", "Slow-steeped cold brew coffee meets crisp tonic - smooth and sparkling with a touch of bitterness."),
        M("Flavoured Cold Brew Tonic", "240", "Naturally infused with fresh fruit notes - clean, bright, and layered with complexity.", variants=[(f, None) for f in ("Orange", "Litchi", "Cranberry", "Yuzu", "Peach", "Kiwi")]),
        M("Espresso Ginger Ale", "240", "Bold espresso over chilled ginger ale - spicy, sweet, and spirited."),
        M("Flavoured Espresso Ginger Ale", "260", "The zing of ginger meets espresso and a refreshing fruit infusion.", variants=[(f, None) for f in ("Orange", "Litchi", "Cranberry", "Yuzu", "Peach", "Kiwi")]),
        M("Cold Brew Ginger Ale", "240", "Chilled cold brew poured over ginger ale for a lively, low-acid coffee refresher."),
        M("Flavoured Cold Brew Ginger Ale", "260", "The ultimate fizzy cold brew with a fruit-kissed finish. Light, clean, and uniquely Meloghrano.", variants=[(f, None) for f in ("Orange", "Litchi", "Cranberry", "Yuzu", "Peach", "Kiwi")]),
        M("Sour Coffee", "270", "A lively blend of litchi, vanilla, and naturally fermented cold brew. Fruity, tangy, and refreshingly effervescent.", tags=["coffee", "probiotic"]),
        M("Tropical Sour Coffee", "280", "Cold brew layered with your choice of fruit infusion and topped with sparkling water - zesty, refreshing, and effervescent.",
          tags=["coffee", "probiotic"], variants=[("Orange", None), ("Cranberry", None), ("Guava", None)]),
    ]),
    category("Manual Brews", "manual-brews", "Slow-brewed by hand with single-origin beans.", {**HOT_COFFEE, "temp": None, "strength": 3, "sweet": 1, "tags": ["coffee", "manual brew"]}, [
        M("V60", "220", "A pour-over technique that brings out clarity and brightness in every cup. Beans: Frozen Cherry, Honey Sundried, Pineapple Blend or Indence.", variants=[("Hot", None), ("Iced", None)]),
        M("Aeropress", "220", "A smooth, full-bodied brew using gentle pressure. Clean, rich, and slightly intense. Beans: Frozen Cherry, Honey Sundried, Pineapple Blend or Indence.", variants=[("Hot", None), ("Iced", None)]),
        M("French Press", "200", "Classic immersion brewing for a bold, deep cup with pronounced body and lingering flavour.", temp="hot", strength=4),
        M("Clever Drip", "200", "A hybrid between pour-over and immersion - smooth, balanced, and accessible.", temp="hot"),
    ]),
    category("Frappes", "frappes", "Chilled, creamy and whipped, made with real coffee.", {**COLD_COFFEE, "strength": 2, "sweet": 4, "tags": ["coffee", "blended"], "addons": ["Whipped Cream"]}, [
        M("Classic Frappe", "260", "A silky blend of espresso, milk, and ice - smooth, foamy, and satisfyingly bold."),
        M("Flavoured Classic Frappe", "280", "Your classic frappe, elevated with naturally sweet flavour infusions.", variants=[("Vanilla", None), ("Hazelnut", None), ("Caramel", None)]),
        M("Mocha Frappe", "280", "Rich espresso meets dark chocolate in this cool, chocolaty treat. Deep, bold, and ultra-satisfying."),
        M("Flavoured Mocha Frappe", "290", "A mocha frappe layered with flavour. Smooth coffee, cocoa, and your choice of a luscious twist.", variants=[("Vanilla", None), ("Hazelnut", None), ("Caramel", None)]),
        M("Affogato Shake", "300", "A bold fusion of your chosen gelato, organic milk, and a shot of espresso - velvety, robust, and finished with a delicate garnish."),
    ]),
    category("Matcha", "matcha", "Ceremonial grade Japanese matcha.", {"type": "beverage", "coffee": False, "tags": ["tea", "matcha"], "addons": MATCHA_EXTRAS, "pairs": ["chocolate", "creamy"]}, [
        M("Matcha Latte", "250", "Ceremonial grade matcha whisked to a frothy finish - earthy, vibrant, and energizing.", temp="hot", sweet=2),
        M("Tender Coconut Iced Matcha", "330", "A tropical twist on tradition. Creamy tender coconut water pairs beautifully with matcha - soothing, mellow, and rehydrating.", temp="cold", sweet=2),
        M("Mango Iced Matcha", "320", "Vibrant and uplifting. Bold ceremonial matcha paired with juicy mango - summer in a glass.", temp="cold", sweet=3),
    ]),
    category("Hot Teas & Chocolate", "hot-teas", "Long-leaf teas and hot chocolate.", TEA, [
        M("Chamomile Tea", "180", "Soothing, floral chamomile blossoms gently steeped for relaxation.", sweet=1, tags=["tea", "herbal"]),
        M("Kashmiri Kahwa", "180", "Spiced green tea with saffron, almonds, and warm aromatics.", sweet=1),
        M("Green Tea", "180", "Pure long-leaf green tea - clean, calming, and rejuvenating.", sweet=1),
        M("Oolong", "230", "Smooth, semi-oxidized tea with floral undertones and soft astringency.", sweet=1),
        M("Maharaja Oolong", "230", "Regal blend of spiced oolong with cardamom and clove - full-bodied and bold.", sweet=1),
        M("Dark Hot Chocolate", "250", "Rich Belgian dark chocolate, steamed to perfection - deep, silky, and decadent.", sweet=4, tags=["chocolate drink"]),
        M("Milk Hot Chocolate", "240", "Comforting and smooth, made with creamy milk and cocoa.", sweet=4, tags=["chocolate drink"]),
        M("Spiced Chocolate", "350", "A decadent fusion of rich chocolate with warming notes of cinnamon and nutmeg. Luxurious, aromatic, and winter-soul satisfying.", sweet=4, tags=["chocolate drink"]),
    ]),
    category("Mocktails & Coolers", "mocktails", "Refreshing non-alcoholic drinks made with real ingredients.", {**COLD_NON_COFFEE, "tags": ["cooler"], "sweet": 3}, [
        M("Virgin Mojito", "180", "A classic Cuban refresher with muddled mint, lime, and soda. Crisp and invigorating.", sweet=2),
        M("Flavoured Mojito", "200", "The mojito, reimagined. Bright fruit infusions paired with fresh mint and fizz.",
          variants=[(f, None) for f in ("Green Apple", "Cranberry", "Yuzu", "Passionfruit", "Peach", "Kiwi", "Elderflower", "Lavender", "Strawberry", "Pineapple")]),
        M("Cola Mojito", "200", "A fizzy fusion of classic cola, fresh mint, lime, and a hint of spice - cool, zesty, and wildly refreshing."),
        M("Coffee Mojito", "220", "A bold blend of espresso, mint, and citrus - a lively, unexpected take on the classic mojito.", coffee=True, tags=["cooler", "coffee"], strength=3),
        M("Flavoured Coffee Mojito", "240", "A daring mix of coffee, herbs, and exotic fruit infusions. Zesty, bold, and balanced.", coffee=True, tags=["cooler", "coffee"], strength=3,
          variants=[(f, None) for f in ("Passionfruit", "Green Apple", "Cranberry", "Peach", "Kiwi", "Elderflower", "Lavender", "Strawberry", "Pineapple")]),
        M("Lemon Iced Tea", "160", "Freshly brewed tea with a splash of lemon. Light, clean, and thirst-quenching.", tags=["tea", "cooler"], sweet=2),
        M("Flavoured Lemon Iced Tea", "180", "Iced tea with a natural flavor boost. Choose your infusion for a subtly sweet, cooling experience.", tags=["tea", "cooler"],
          variants=[(f, None) for f in ("Peach", "Green Apple", "Cranberry", "Strawberry", "Passionfruit", "Kiwi", "Yuzu", "Elderflower", "Lavender", "Pineapple")]),
        M("Chilli Guava", "210", "Sweet pink guava blended with a touch of red chilli, lime, and salt. Spicy, tangy, and irresistibly tropical."),
        M("Early Sunset", "250", "Orange and cranberry - juicy orange meets tart cranberry in this citrus-forward refresher with a smooth, sunset finish."),
        M("Green Champion", "200", "Fresh basil muddled into crisp sparkling water - herbal, cooling, and uplifting.", sweet=1),
        M("Lagoon Fizz", "280", "Blue curacao, orange, yuzu, coconut and sparkling water - a vibrant medley of tropical flavours."),
        M("Virgin Pina Colada", "280", "Creamy coconut and juicy pineapple blended into a smooth tropical classic. No alcohol, just sunshine in a glass.", sweet=4),
        M("Chill Granate", "280", "Litchi, cranberry, pomegranate and lemon - a tangy, fruit-forward mocktail. Cool and invigorating."),
        M("Golden Granate", "280", "Orange, mixed berries, pomegranate, mint and lemon - citrus and berry brightness in a vibrant, zesty blend."),
    ]),
    category("Shakes & Smoothies", "shakes-smoothies", "Thick shakes, and smoothies made with real fruit (dairy-free per the menu).", {**COLD_NON_COFFEE, "tags": ["shake"], "sweet": 4, "pairs": ["chocolate", "nutty"]}, [
        M("Chocolate Shake", "230", "A timeless indulgence. Velvety and bold with rich cocoa, served thick and frosty.", addons=["Whipped Cream"]),
        M("Strawberry Shake", "230", "Lush and fruity with handpicked strawberries. Creamy, naturally sweet, and utterly refreshing.", addons=["Whipped Cream"]),
        M("Red Berry Shake", "240", "A blend of mixed berries - tart, sweet, and vibrant.", addons=["Whipped Cream"]),
        M("Hazelnut Brownie Shake", "260", "Decadent and nutty with chunks of fudgy brownie, finished with whipped cream on top.", addons=["Whipped Cream"]),
        M("Kit Kat Shake", "260", "Crunchy Kit Kat wafers crushed into a cold, creamy base, crowned with a swirl of whipped cream.", addons=["Whipped Cream"]),
        M("Oreo Shake", "260", "Classic Oreo cookies swirled into vanilla milkshake, topped with whipped cream.", addons=["Whipped Cream"]),
        M("Gelato Shake", "290", "Your choice of artisanal gelato blended with organic milk and finished with a handcrafted garnish.", addons=["Whipped Cream"]),
        M("Alphonso Mango Smoothie", "260", "Made with ripe Alphonso mangoes - thick, tropical, and bursting with golden sweetness.", tags=["shake", "smoothie"], sweet=3),
        M("Strawberry Smoothie", "280", "Fresh strawberries blended into a creamy, pink pour. Sweet, tart, and naturally refreshing.", tags=["shake", "smoothie"], sweet=3),
        M("Mixed Berry Smoothie", "280", "A vibrant mix of blueberries, raspberries, and strawberries.", tags=["shake", "smoothie"], sweet=3),
    ]),
    category("All-Day Breakfast", "all-day-breakfast", "Eggs, omelettes and breakfast plates.", {**FOOD, "tags": ["breakfast"], "pairs": ["creamy", "cocoa", "orange"]}, [
        M("Shakshuka", "380", "Poached eggs in a robust tomato, olive, bell pepper, onion, and garlic sauce. Served with toasted bread.", addons=BREAKFAST_EXTRAS),
        M("Pita Bread Plate", "240", "Warm pita bread served with salad and hummus or scrambled eggs.", egg=False,
          variants=[("With hummus", "240"), ("With scrambled eggs", "290")]),
        M("French Omelette", "220", "Custard-style French omelette, seasoned with salt and pepper. Served with sauteed vegetables and hashbrown.", addons=BREAKFAST_EXTRAS),
        M("Spanish Omelette", "230", "Potatoes and onions folded into a fluffy omelette. Served with sauteed vegetables and hashbrown.", addons=BREAKFAST_EXTRAS),
        M("Sunny Side Up", "220", "Perfectly cooked eggs with runny yolks and lightly crisp edges.", addons=BREAKFAST_EXTRAS),
        M("Masala Omelette", "230", "Indian-style omelette with onions, tomatoes, chillies, and coriander.", addons=BREAKFAST_EXTRAS),
        M("Cheese Omelette", "220", "Fluffy omelette filled with melted cheese.", addons=BREAKFAST_EXTRAS),
        M("Mushroom Omelette", "240", "Savory omelette with sauteed mushrooms.", addons=BREAKFAST_EXTRAS),
        M("Scrambled Eggs", "210", "Creamy scrambled eggs with milk, salt, and pepper.", addons=BREAKFAST_EXTRAS),
        M("Classic French Toast", "280", "Golden brioche slices soaked in cinnamon-vanilla egg custard. Served with maple syrup and butter.", type="dessert"),
        M("Berry Bliss French Toast", "330", "Topped with seasonal berries, berry compote, and icing sugar. Served with whipped cream or Greek yogurt.", type="dessert", egg=True),
        M("Nutella Banana French Toast", "340", "Stuffed with Nutella and layered with caramelised bananas. Finished with chocolate drizzle and toasted hazelnuts.", type="dessert", egg=True),
        M("Lotus Biscoff French Toast", "350", "Smothered in Biscoff spread, topped with cookie crumbles and vanilla cream.", type="dessert", egg=True),
        M("Savory Herb French Toast", "290", "Herb- and cheese-infused savory French toast with spiced egg custard. Served with sauteed veggies and hashbrown."),
        M("Burrata Basil French Toast", "370", "Crispy toast topped with creamy burrata, cherry tomatoes, and basil pesto - sweet meets savoury.", egg=True),
        M("Breakfast Veg Plate", "450", "Hash brown, sauteed veggies, bread toast, avocado salad, grilled tomato with fresh mozzarella, and baked beans.", serves=1),
        M("Breakfast Egg Plate", "480", "Mashed potatoes, grilled eggs or eggs to order, bread toast, avocado salad, baked beans, and sauteed vegetables."),
        M("Burrata Croissant", "450", "Buttery croissant with basil pesto, burrata, tomato, toasted walnuts, and mixed seeds.", featured=True),
        M("Brioche Egg", "390", "Brioche bun filled with spiced or creamy scrambled eggs."),
        M("Creamy Mushroom & Spinach Croissant", "390", "Butter croissant filled with creamy mushroom and spinach."),
    ]),
    category("Salads & Soups", "salads-soups", "Fresh salads and comforting soups.", {**FOOD, "tags": ["salad"]}, [
        M("Caesar Salad", "290", "Crisp iceberg lettuce, English cucumber, cherry tomatoes, tossed in creamy Caesar dressing, olives. Topped with golden croutons and shaved Parmesan.", addons=SALAD_EXTRAS),
        M("Tortellini Salad", "350", "Spinach, cherry tomatoes, artichokes, fresh basil, dill, and Parmesan, tossed in a tangy red wine vinegar dressing.", addons=SALAD_EXTRAS),
        M("Chickpea Salad", "280", "Cucumber, cherry tomatoes, bell peppers, coriander leaves, avocado, chickpeas, red onion, and feta cheese, with a classic balsamic vinegar dressing.", addons=SALAD_EXTRAS),
        M("Watermelon Feta Salad", "270", "Juicy watermelon and mint paired with crumbled feta, lemon-mint dressing, and a balsamic glaze.", addons=SALAD_EXTRAS),
        M("Waldorf Salad", "380", "Red and green apples, grapes, caramelized walnuts, and fresh lettuce in a honey-Parmesan dressing.", addons=SALAD_EXTRAS),
        M("Peanut Salad", "330", "Cherry tomatoes, cucumber, carrot, roasted peanuts, purple cabbage, and lettuce with a spicy honey-peanut dressing.", addons=SALAD_EXTRAS),
        M("Avocado Salad", "430", "Avocado, cucumber, cherry tomatoes, olives, pumpkin seeds, grapes, purple cabbage and apple in a Greek dressing.", addons=SALAD_EXTRAS),
        M("Cherry-Pineapple Cheese Picks", "360", "Creamy artisanal cheese, sun-ripened pineapple, and glazed cherry skewered and presented on crisp lettuce over hand-laid ice.", tags=["salad", "starter"]),
        M("Butternut Soup", "350", "Slow-roasted butternut squash blended with Thai chili, rosemary, and thyme. Finished with olive oil and cracked pepper.", tags=["soup"], temp="hot"),
        M("Broccoli Soup", "350", "A vibrant puree of tender broccoli, simmered with herbs and a touch of cream.", tags=["soup"], temp="hot"),
        M("Cream of Mushroom", "350", "A velvety blend of button and shiitake mushrooms, slow-sauteed with herbs, finished with cream and cracked pepper.", tags=["soup"], temp="hot"),
        M("Zuppa di Pomodoro", "350", "Slow-roasted tomatoes blended with basil and extra virgin olive oil. Rich, tangy, and comforting.", tags=["soup"], temp="hot"),
    ]),
    category("Appetizers", "appetizers", "Small plates and sides.", {**FOOD, "tags": ["starter"]}, [
        M("Raw Banana Cutlet", "260", "Raw banana marinated and crumb-fried. Served with a refreshing mint yogurt dip."),
        M("Cheese Sticks with Podi Masala", "350", "Classic mozzarella sticks with an Indian twist. Served with roasted bell pepper dip."),
        M("Deviled Eggs", "280", "Tri-color egg whites filled with a creamy yolk mixture. Served with a mixed lettuce salad."),
        M("Crumb Fried Mushroom", "350", "Cheesy stuffed mushrooms, crumb-fried and served with peri peri mayo."),
        M("Beet and Nut", "340", "Chef's special. Shredded beetroot shaped into nuggets and crumb fried with nuts."),
        M("Mushroom Parmesana", "370", "Baked mushrooms stuffed with garlic, chilli flakes, oregano, and melted cheese - rich, earthy, and indulgent."),
        M("Zestini Stacks", "390", "A vibrant stack of mushroom, zucchini, and cherry tomato, dressed with zesty mustard, olive oil, garlic, and fresh herbs."),
        M("Spicy Grilled Pineapple", "280", "Char-grilled pineapple slices with a spicy twist."),
        M("Popcorn Mushroom", "310", "Crispy mushroom bites, golden-fried to perfection."),
        M("Corn Cheese Bites", "300", "Golden-fried bites filled with sweet corn and melted cheese. Served with spicy dip."),
        M("Creamy Grilled Broccoli", "370", "Broccoli marinated in a creamy garlic sauce and grilled to perfection."),
        M("Stuffed Grilled Mushroom", "370", "Grilled mushrooms stuffed with cheese and herbs."),
        M("Creamy Garlic Pepper Paneer", "450", "Cottage cheese grilled in a creamy marinade with secret seasonings."),
        M("Grilled Paneer", "420", "Spicy. Tender paneer chunks marinated in vibrant cilantro pesto, grilled and served with a fresh leafy salad."),
        M("Quadro Garlic Bread", "390", "Garlic bread topped with four cheeses - Provolone, Grana Padano, Mozzarella, and Burrata.", tags=["starter", "bread"]),
        M("Onion Rings", "270", "Crispy golden-fried onion rings."),
        M("French Fries", "200", "Golden fried potato sticks.", addons=["Peri Peri (fries)", "Cheese (fries)"]),
        M("Nachos", "370", "Homemade nachos topped with cheese sauce, jalapenos, spring onion, bean sauce, tomato salsa, and sour cream.", tags=["starter", "shareable"]),
        M("Hash Brownie", "200", "Crispy hash browns served with ketchup and mayonnaise."),
    ]),
    category("Sourdough & Breads", "sourdough", "Wood-fired sourdough: open toasts, sandwiches, small breads, panuozzo and calzones.", {**FOOD, "tags": ["sourdough"]}, [
        M("Sourdough Garlic Bread", "200", "Freshly baked bread brushed with garlic, herbs, and olive oil. Served with your choice of dip.", tags=["sourdough", "bread"],
          variants=[("Garlic Aioli dip", None), ("Roasted Bell Pepper dip", None), ("Classic Cheese dip", None)], addons=DIPS),
        M("Sourdough Rosemary Bread", "220", "Handcrafted sourdough focaccia infused with fresh rosemary and extra virgin olive oil.", tags=["sourdough", "bread"], addons=DIPS),
        M("Chilli Cheese Toast", "270", "Toasted sourdough topped with green chillies and melted cheese - crisp, spicy, and comforting.", tags=["sourdough", "toast"]),
        M("Pesto Mushroom Toast", "310", "A vibrant layer of basil pesto topped with grilled mushroom chunks on toasted sourdough.", tags=["sourdough", "toast"]),
        M("Egg Toast", "350", "Toasted sourdough topped with creamy egg spread and grilled egg chunks.", tags=["sourdough", "toast"]),
        M("Margherita Toast", "380", "Toasted sourdough with grilled tomatoes and fresh mozzarella - a rustic favorite.", tags=["sourdough", "toast"]),
        M("Bruschetta", "350", "Classic Italian toast topped with zesty tomato salsa, garlic, and fresh herbs.", tags=["sourdough", "toast"]),
        M("Veg Club Sandwich", "390", "Sauteed veggies, coleslaw, honey mustard dip, and cheese grilled between sourdough bread. Served with fries.", tags=["sourdough", "sandwich"],
          variants=[("Sourdough", None), ("Focaccia", None), ("Ciabatta", None), ("Olive Bread", None)]),
        M("Egg Sandwich", "450", "Lettuce, egg omelette, and cheese sauce grilled between sourdough bread. Served with fries.", tags=["sourdough", "sandwich"],
          variants=[("Sourdough", None), ("Focaccia", None), ("Ciabatta", None), ("Olive Bread", None)]),
        M("Avocado Sandwich", "550", "Homemade guacamole, onion, cucumber, and cheese. Served with fries.", tags=["sourdough", "sandwich"],
          variants=[("Sourdough", None), ("Focaccia", None), ("Ciabatta", None), ("Olive Bread", None)]),
        M("Creamy Mushroom & Spinach Sandwich", "410", "Creamy mushroom and spinach filling with cheese, grilled to perfection.", tags=["sourdough", "sandwich"],
          variants=[("Sourdough", None), ("Focaccia", None), ("Ciabatta", None), ("Olive Bread", None)]),
        M("Caramelised Onion Small Bread", "310", "Topped with four kinds of cheese and slow-cooked caramelised onions.", tags=["sourdough", "bread"]),
        M("Sundried Tomato Small Bread", "290", "Homemade tomato sauce, fresh mozzarella, and basil on a crispy base.", tags=["sourdough", "bread"]),
        M("Cheese Garlic Small Bread", "340", "Topped with mushrooms, bell peppers, olives, and cheese on a garlic-infused base.", tags=["sourdough", "bread"]),
        M("Chef's Special Small Bread", "350", "Create your own: choose any three toppings - mushroom, sundried tomato, veggies, cheese, jalapeno, olives, corn, bird's eye chilli, bell peppers.", tags=["sourdough", "bread"]),
        M("Classic Margherita Panuozzo", "320", "Fresh mozzarella, arugula, homemade tomato sauce, and basil in wood-fired sourdough.", tags=["sourdough", "sandwich", "panuozzo"]),
        M("Peri Peri Paneer Panuozzo", "380", "Grilled paneer, sauteed onions, jalapenos, and garlic mayo.", tags=["sourdough", "sandwich", "panuozzo"]),
        M("Mushroom Truffle Panuozzo", "430", "Sauteed mushrooms, truffle oil, arugula, and a creamy cheese sauce - rich, earthy, and indulgent.", tags=["sourdough", "sandwich", "panuozzo"]),
        M("Burrata & Pesto Panuozzo", "410", "Creamy burrata, fresh basil pesto, arugula, cherry tomatoes, and mixed seeds.", tags=["sourdough", "sandwich", "panuozzo"]),
        M("Peri Peri Paneer Calzone", "400", "Grilled paneer mixed with a creamy cheese blend and spiced with house-made peri peri seasoning. Golden-fried.", tags=["calzone"]),
        M("Pesto Olive Calzone", "350", "Green and black olives folded into fresh homemade basil pesto, wrapped and fried until crisp.", tags=["calzone"]),
        M("Cheese Garlic Calzone", "360", "Fresh mozzarella, garlic, and homemade tomato sauce, topped with grated mozzarella.", tags=["calzone"]),
        M("Mushroom Truffle Calzone", "450", "Sauteed button and shiitake mushrooms with truffle oil and fresh mozzarella in a crispy shell.", tags=["calzone"]),
    ]),
    category("Sourdough Pizzas", "sourdough-pizzas", "Special menu: hand-stretched, wood-fired sourdough pizzas in 8 or 12 inch.", {**FOOD, "tags": ["pizza", "sourdough"]}, [
        M("Smokey Pesto Burrata Pizza", "900", None, variants=[("8 inch", "900"), ("12 inch", "1350")], featured=True),
        M("Trio Veganza Pizza", "800", None, variants=[("8 inch", "800"), ("12 inch", "1200")]),
        M("Loaded Farmhouse Pizza", "650", None, variants=[("8 inch", "650"), ("12 inch", "950")]),
        M("Peri Peri Paneer Pizza", "700", None, variants=[("8 inch", "700"), ("12 inch", "1000")]),
        M("Smokey BBQ Grill Veg Pizza", "650", None, variants=[("8 inch", "650"), ("12 inch", "950")]),
        M("Hawaiian Pizza", "600", None, variants=[("8 inch", "600"), ("12 inch", "850")]),
    ]),
    category("Mains & Pasta", "mains-pasta", "Risottos, platters, steaks and pastas.", {**FOOD, "tags": ["main"]}, [
        M("Mushroom Risotto", "390", "Traditional Italian rice dish with mushrooms, white wine, and Parmesan."),
        M("Mushroom & Veg Stroganoff", "450", "Creamy mushroom and vegetable stew served with herb rice."),
        M("Corn Steak", "440", "Grilled corn and veggie patty served with herb rice and mashed potato and a refreshing rava dip."),
        M("Mac and Cheese", "310", "Classic creamy mac and cheese baked to golden perfection. Option to add vegetables.",
          variants=[("Classic", "310"), ("With veggies", "360")], tags=["main", "pasta"]),
        M("Mexican Rice Platter - Veg", "390", "Mildly spiced Mexican-style rice (or herb rice), served with sauteed vegetables, crispy lavash, and a refreshing rava dip."),
        M("Mexican Rice Platter - Egg", "440", "Mildly spiced Mexican-style rice (or herb rice), served with sauteed vegetables, spiced egg, crispy lavash, and a refreshing rava dip."),
        M("Grilled Egg Platter", "390", "Spicy grilled egg served with sauteed vegetables, creamy mashed potato, and a rich butter garlic sauce."),
        M("Soya Steak", "430", "Hearty soya steak paired with sauteed vegetables, mashed potato, and a flavorful mushroom pepper sauce."),
        M("Vegetable Au Gratin", "380", "Baked creamy, cheesy vegetables served with garlic bread."),
        M("Gnocchi", "370", "Soft, pillowy potato dumplings tossed in two sauces - creamy Alfredo and tangy Arrabbiata.", tags=["main", "pasta"]),
        M("Alfredo Pasta", "420", "Rich Alfredo sauce with veggies.", tags=["main", "pasta"], variants=PASTA_CHOICE),
        M("Arrabbiata Pasta", "390", "Tomato-based pasta with garlic bread.", tags=["main", "pasta"], variants=PASTA_CHOICE),
        M("Butternut Squash Pasta", "460", "Creamy roasted garlic and butternut squash with veggies.", tags=["main", "pasta"], variants=PASTA_CHOICE),
        M("Pesto Pasta", "480", "Basil pesto sauce tossed with vegetables.", tags=["main", "pasta"], variants=PASTA_CHOICE),
        M("Spaghetti Aglio e Olio", "450", "Garlic and olive oil tossed with spaghetti, chilli flakes, and Parmesan - simple and bold.", tags=["main", "pasta"]),
        M("Florentine Pasta", "450", "Creamy homemade mushroom sauce with spinach and cheese. Fettuccine.", tags=["main", "pasta"]),
        M("Fajita Pasta", "460", "Fajita sauce with bell peppers, mushrooms, and zucchini. Fettuccine.", tags=["main", "pasta"]),
        M("Classic Lasagna", "460", "Traditional layered pasta with tomato sauce and cheese sauce.", tags=["main", "pasta"]),
        M("Pink Sauce Pasta", "450", "Alfredo and Arrabbiata blended with veggies.", tags=["main", "pasta"], variants=PASTA_CHOICE),
    ]),
    category("Wraps", "wraps", "Served with fries.", {**FOOD, "tags": ["wrap"], "addons": WRAP_EXTRAS}, [
        M("Paneer Wrap", "380", "Grilled paneer with fresh veggies and green chutney, wrapped and served with fries."),
        M("Egg Wrap", "350", "High-protein egg mixture with sliced egg, onion, and iceberg lettuce. Served with fries."),
        M("Mushroom Wrap", "370", "Sauteed mushrooms with spinach, onions, tomatoes, jalapenos, and garlic aioli. Served with fries."),
        M("Mediterranean Wrap", "330", "Falafel with hummus and lettuce wrapped and served with fries."),
    ]),
    category("Sundaes & Desserts", "desserts", "Sundaes, sizzlers and classic desserts.", {**DESSERT, "sweet": 5, "tags": ["dessert"]}, [
        M("Death by Chocolate", "320", "Chocolate cake layered with one scoop of vanilla gelato, two scoops of chocolate gelato, rich fudge sauce, roasted nuts, and whipped cream.", addons=SUNDAE_EXTRAS),
        M("Lotus Dream Delight", "300", "Crumbled Biscoff cookies, Biscoff gelato, brownie chunks, and a scoop of vanilla - indulgent, spiced, and comforting.", addons=SUNDAE_EXTRAS),
        M("Banana Split", "330", "A classic split banana with one scoop each of vanilla gelato, chocolate gelato, and fruit sorbet. Finished with chocolate sauce, nuts, and whipped cream.", addons=SUNDAE_EXTRAS),
        M("Melt My Cookie", "340", "Wheat cookie dough served warm on a sizzling plate, topped with vanilla gelato, chocolate sauce, and roasted nuts.", addons=SUNDAE_EXTRAS, featured=True),
        M("Hot Sizzling Brownie", "300", "Rich brownie served on a sizzling plate, drenched in fudge sauce and sprinkled with crunchy nuts. (Contains egg)", addons=SUNDAE_EXTRAS),
        M("Classic Tiramisu", "330", "An Italian classic made with espresso-soaked ladyfingers layered with creamy mascarpone and dusted with cocoa.", coffee=True, addons=["Fresh Chocolate Sauce"], featured=True),
        M("Classic Tres Leches", "330", "A light sponge cake soaked in a rich blend of three milks, topped with airy whipped cream. (Contains egg)", addons=["Fresh Chocolate Sauce"]),
        M("Basque Cheesecake", "320", "Creamy, crustless cheesecake with a caramelized top and rich, velvety center. (Contains egg)", addons=["Fresh Chocolate Sauce"]),
    ]),
    category("Seasonal Specials", "seasonal-specials", "From the café's special menu.", {**HOT_COFFEE, "sweet": 4, "strength": 2}, [
        M("Vanilla Cinnamon Coffee", "260", "Speciality hot coffee."),
        M("Maple Cream Coffee", "270", "Speciality hot coffee."),
        M("Ginger Bread Coffee", "270", "Speciality hot coffee."),
        M("White Chocolate Peppermint Coffee", "270", "Speciality hot coffee."),
        M("Caramel Vanilla Coffee", "270", "Speciality hot coffee."),
        M("Orange Spice Holiday Coffee", "280", "Speciality hot coffee."),
        M("Almond Joy Morning Coffee", "280", "Speciality hot coffee."),
        M("Mocha Christmas Morning", "280", "Speciality hot coffee."),
        M("Iced Tiramisu Latte", "320", "Signature cold latte.", temp="cold"),
        M("Pistachio Tiramisu Latte", "330", "Signature cold latte.", temp="cold"),
        M("Cozy Nutmeg Latte", "280", "Signature cold latte.", temp="cold"),
        M("Litchi Blossom", "270", "A delicate mix of litchi juice, rose syrup and ginger ale.", **{**COLD_NON_COFFEE, "tags": ["cooler"], "sweet": 3, "strength": None}),
        M("Brownie Shake", "280", "Rich chocolate, fudgy brownie and creamy goodness in every sip.", **{**COLD_NON_COFFEE, "tags": ["shake"], "sweet": 5, "strength": None}),
    ]),
]

# The printed menu splits coffee into many sections (classic hot, flavoured
# lattes, Rockline specials, iced, cold brews, sparkling, probiotic, manual
# brews). The app groups them into Hot Coffee and Cold Coffee so the category
# bar stays short; every item keeps its own attributes. Non-coffee seasonal
# drinks move to their natural sections.
COFFEE_SECTIONS = {
    "classic-hot-coffees", "signature-lattes", "rockline-specials", "classic-iced-coffees", "cold-brews",
    "sparkling-coffee", "manual-brews", "frappes", "seasonal-specials",
}


def _group_coffee(categories):
    hot, cold, rest = [], [], []
    by_slug = {c["slug"]: c for c in categories}
    for cat in categories:
        if cat["slug"] not in COFFEE_SECTIONS:
            rest.append(cat)
            continue
        for it in cat["items"]:
            if not it["contains_coffee"]:
                by_slug["shakes-smoothies" if "shake" in it["tags"] else "mocktails"]["items"].append(it)
            elif it["temperature"] == "cold":
                cold.append(it)
            else:  # hot, or served either way (Rockline lattes, V60 / Aeropress)
                hot.append(it)
    return [
        dict(name="Hot Coffee", slug="hot-coffee", items=hot,
             description="Espresso classics, flavoured and signature lattes, and hand brews (V60 and Aeropress can be iced)."),
        dict(name="Cold Coffee", slug="cold-coffee", items=cold,
             description="Iced coffees, cold brews, sparkling and probiotic coffees, and frappes."),
        *rest,
    ]


CATEGORIES = _group_coffee(CATEGORIES)

MELOGHRANO = {
    "restaurant": dict(
        slug="meloghrano",
        name="Meloghrano Cafe",
        tagline="Flavours that tell stories - Italian, pizza & specialty coffee",
        address_line="3801, 13th Cross, Banashankari 2nd Stage, Basavanagudi",
        city="Bengaluru",
        phone="+91 76766 40373",
        currency="INR",
    ),
    "settings": dict(
        assistant_name="Meloghrano Guide",
        welcome_message=(
            "Ciao! Craving wood-fired sourdough pizza, a creamy pasta or something sweet? Tell me your mood "
            "and budget and I'll find it on the menu."
        ),
        suggested_prompts=[
            "Suggest a pizza for two",
            "Show me pasta under ₹450",
            "Something cheesy to share",
            "What dessert goes with a cappuccino?",
            "A cold drink that isn't coffee",
        ],
        brand_color="#8E2433",
        assistant_icon="utensils",
        ai_enabled=True,
        pickup_enabled=True,
        ordering_enabled=False,
        allergen_disclaimer=(
            "Allergen and dietary details for this menu haven't been verified with the café. "
            "Please check with staff before ordering if you have an allergy."
        ),
    ),
    "addons": ADDONS,
    "categories": CATEGORIES,
}
