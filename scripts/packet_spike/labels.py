# Ground truth, read by hand from the photos. None = not visible / not stated (the reader should say null).
F, S, J = "Mr Fothergill's", "Suttons", "Johnsons"
LABELS = {
 "10490152": dict(name="Coriander", variety="Cilantro", supplier=F, seeds=150, depth=5, g=(14, 21), bb=None),
 "10490821": dict(name="Parsley", variety="Afrodite", supplier=F, seeds=500, depth=15, g=(14, 21), bb=None),
 "10492582": dict(name="Pea", variety="Blauwschokker", supplier=S, seeds=100, depth=50, g=(7, 10), bb=2025),
 "10493270": dict(name="Pea", variety="Snak Hero", supplier=F, seeds=None, depth=50, g=(10, 18), bb=2026),
 "10494213": dict(name="Pea", variety="Sweet Sahara", supplier=F, seeds=250, depth=50, g=(10, 18), bb=2026),
 "10500226": dict(name="Nasturtium", variety=None, supplier=F, seeds=None, depth=15, g=(21, 28), bb=2027),
 "10502225": dict(name="Cabbage", variety="Greyhound", supplier=F, seeds=250, depth=15, g=(14, 21), bb=None),
 "10503428": dict(name="Borage", variety=None, supplier=S, seeds=70, depth=13, g=None, bb=2024),
 "10504555": dict(name="Carrot", variety="Flyaway F1", supplier=F, seeds=500, depth=15, g=(14, 21), bb=2028),
 "10504877": dict(name="Parsley", variety="Moss Curled 2", supplier=F, seeds=500, depth=15, g=(14, 21), bb=None),
 "10510384": dict(name="Cucumber", variety="Chinese Slangen", supplier=F, seeds=None, depth=5, g=(7, 14), bb=2027),
 "10512285": dict(name="Dill", variety=None, supplier=F, seeds=375, depth=15, g=(14, 21), bb=None),
 "10523810": dict(name="Carrot", variety="Chantenay Red Cored 2", supplier=F, seeds=1000, depth=15, g=(14, 21), bb=None),
 "10524827": dict(name="Sunflower", variety="Sun King", supplier=F, seeds=20, depth=15, g=(14, 21), bb=None),
 "10530221": dict(name="Coriander", variety="Filtro", supplier=J, seeds=150, depth=None, g=(14, 21), bb=2027),
 "10531062": dict(name="Carrot", variety="Maestro F1", supplier=S, seeds=600, depth=13, g=(15, 20), bb=2028),
 "10531572": dict(name="Rocket", variety=None, supplier=S, seeds=350, depth=None, g=None, bb=2027),
 "10532083": dict(name="Lettuce", variety="All The Year Round", supplier=S, seeds=1000, depth=13, g=(6, 12), bb=2027),
 "10532610": dict(name="Leaf Salad", variety="Lettuce Mix", supplier=S, seeds=1500, depth=None, g=None, bb=2028),
 "10533124": dict(name="Spring Onion", variety="Marksman", supplier=S, seeds=150, depth=13, g=None, bb=2028),
 "10533676": dict(name="Coriander", variety="for Seed", supplier=J, seeds=150, depth=None, g=(14, 21), bb=2027),
 "10534210": dict(name="?", variety=None, supplier=J, seeds=None, depth=None, g=(14, 28), bb=2027),   # name torn off
 "10535631": dict(name="?", variety=None, supplier=S, seeds=None, depth=None, g=None, bb=2024),       # name hidden by a finger
}
# Calendar truth, from the photos (graphics adjudicated by eye) or the printed months (Johnsons: only what is stated)
CAL = {
 "10490152": {"sow_indoors": range(1, 13), "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(1, 13)},
 "10490821": {"sow_indoors": range(1, 13), "sow_outdoors": range(3, 8), "plant_out": [], "harvest": range(1, 13)},
 "10492582": {"sow_indoors": [], "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(6, 11)},
 "10493270": {"sow_indoors": [], "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(5, 10)},
 "10494213": {"sow_indoors": [], "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(5, 10)},
 "10500226": {"sow_indoors": range(2, 6), "sow_outdoors": range(4, 7), "plant_out": [5, 6], "harvest": range(6, 11)},
 "10502225": {"sow_indoors": range(3, 6), "sow_outdoors": range(3, 6), "plant_out": [5, 6], "harvest": range(6, 10)},
 "10503428": {"sow_indoors": [], "sow_outdoors": range(4, 7), "plant_out": [], "harvest": range(7, 11)},
 "10504555": {"sow_indoors": [], "sow_outdoors": range(3, 8), "plant_out": [], "harvest": range(6, 12)},
 "10504877": {"sow_indoors": range(1, 13), "sow_outdoors": range(3, 8), "plant_out": [], "harvest": range(1, 13)},
 "10510384": {"sow_indoors": range(2, 5), "sow_outdoors": range(5, 7), "plant_out": [5, 6], "harvest": range(7, 11)},
 "10512285": {"sow_indoors": range(1, 13), "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(1, 13)},
 "10523810": {"sow_indoors": [], "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(6, 12)},
 "10524827": {"sow_indoors": range(3, 6), "sow_outdoors": range(3, 6), "plant_out": [5, 6], "harvest": range(6, 10)},
 "10531062": {"sow_indoors": [], "sow_outdoors": range(3, 7), "plant_out": [], "harvest": range(8, 13)},
 "10531572": {"sow_indoors": [], "sow_outdoors": range(4, 7), "plant_out": [], "harvest": range(6, 10)},
 "10532083": {"sow_indoors": [], "sow_outdoors": range(3, 8), "plant_out": [], "harvest": range(5, 11)},
 "10532610": {"sow_indoors": [], "sow_outdoors": range(4, 9), "plant_out": [], "harvest": range(5, 11)},
 "10533124": {"sow_indoors": [], "sow_outdoors": range(3, 9), "plant_out": [], "harvest": range(4, 11)},
 "10535631": {"sow_indoors": [], "sow_outdoors": range(1, 13), "plant_out": [], "harvest": range(1, 13)},
}
TEXT_CAL = {  # printed in words only; just what the packet states
 "10530221": {"sow_outdoors": range(3, 7)},
 "10533676": {"sow_outdoors": range(3, 7), "harvest": range(6, 11)},
 "10534210": {"sow_outdoors": range(3, 8)},
}
