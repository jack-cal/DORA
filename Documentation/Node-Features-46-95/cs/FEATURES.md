# SUMUWW · 0.57.46 / 0.6.95

Uzel přidává dotazy na poplatky, kontrolu před odesláním, stav náhrady RBF a čtení dat v pořadí bloků. Náhrada se ověří před odstraněním čekajících transakcí. Vícenásobné podpisy a uzamčené výstupy jsou implementovány pro oddělené testy aktivace; ve veřejné síti zatím nejsou aktivní.

1 SMW = 100 000 000 yugeon. Automatické poplatky nabízejí tři úrovně podle místních pozorování, bez záruky času potvrzení. Sazbu v yugeon/vB lze zadat ručně. Před odesláním ověřte konečný poplatek a součet v SMW. Odmítnutá transakce nesníží zůstatek.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automatický poplatek zohledňuje objem čekajících dat, kapacitu bloků a prioritu transakcí. Poplatky z minulých bloků nepoužívá. Při malé frontě platí minimální sazba. Náhled se aktualizuje; konečné potvrzení poplatek zafixuje. Pozorování se týká připojeného místního uzlu, nikoli všech uzlů.

Historie nahrazení zaznamenaná tímto uzlem zůstává zachována po restartu peněženky. Odstraněné transakce nemění zůstatek.

Průzkumník zobrazuje odhalené podmínky více podpisů a uzamčení výstupů. Aktivace ve veřejné síti zatím není naplánována.


Historie těžby zobrazuje zvlášť novou emisi, poplatky a celkovou odměnu každého bloku. Částka přijatá vaší peněženkou je uvedena samostatně. Při částečném vyzvednutí se rozdělení mezi složkami nepředpokládá. Uzel poskytuje 28 metod RPC včetně odhadu poplatků a ověřuje a předává podepsané transakce.
