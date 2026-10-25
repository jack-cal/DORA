# SUMUWW · 0.57.46 / 0.6.95

Węzeł udostępnia zapytania o opłaty, kontrolę przed wysłaniem, stan zastąpienia RBF oraz dane w kolejności bloków. Transakcja zastępująca jest sprawdzana przed usunięciem oczekujących transakcji. Wielopodpis i blokady wyjść są zaimplementowane do izolowanych testów aktywacji; nie są jeszcze aktywne w sieci publicznej.

1 SMW = 100 000 000 yugeon. Opłaty automatyczne oferują trzy poziomy na podstawie lokalnych obserwacji, bez gwarancji czasu potwierdzenia. Możesz wpisać stawkę w yugeon/vB. Przed wysłaniem sprawdź końcową opłatę i sumę w SMW. Odrzucona transakcja nie zmniejsza salda.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Opłata automatyczna uwzględnia ilość oczekujących danych, pojemność bloków i priorytet transakcji. Nie używa opłat z wcześniejszych bloków. Przy małej kolejce obowiązuje stawka minimalna. Podgląd jest odświeżany; końcowe potwierdzenie ustala opłatę. Obserwacje dotyczą połączonego lokalnego węzła, nie wszystkich węzłów.

Historia zastąpień zarejestrowanych przez ten węzeł pozostaje dostępna po ponownym uruchomieniu portfela. Usunięte transakcje nie wpływają na saldo.

Eksplorator pokazuje ujawnione warunki wielopodpisu i blokady wyjść. Termin aktywacji w sieci publicznej nie został ustalony.


Historia wydobycia pokazuje osobno nową emisję, opłaty i łączną nagrodę każdego bloku. Kwota otrzymana przez portfel jest wyświetlana oddzielnie. Przy częściowym odebraniu nagrody nie zakłada się podziału jej składników. Węzeł udostępnia 28 metod RPC, w tym szacowanie opłat, oraz weryfikuje i rozsyła podpisane transakcje.
