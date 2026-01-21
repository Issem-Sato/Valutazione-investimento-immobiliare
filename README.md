# Valutazione investimento immobiliare

Questo repository contiene un piccolo **modulo Python** e un **notebook Jupyter** per simulare un investimento immobiliare con:

- **Mutuo** con due modalità di ammortamento:
  - `rata_fissa` (piano “alla francese” / annuità)
  - `quota_capitale_fissa`
- **Cash flow mensile** dell’investimento (affitto − rata) con **tassazione annuale** applicata a fine anno
- Possibilità di distinguere tra **durata del prestito** e **vita del progetto** (es. mutuo 20 anni, progetto 50 anni)
- Calcolo del **VAN (Valore Attuale Netto)** con un tasso di attualizzazione annuo
- Esportazione dei risultati in **DataFrame** (se `pandas` è disponibile)
- Visualizzazioni nel notebook tramite **Plotly**

## Struttura del progetto

- `modulo_investimento.py` – logica e calcoli (classe `ProgettoImmobiliare`)
- `investimento_immobiliare.ipynb` – esempio d’uso + grafici interattivi

## Requisiti

- **Python 3.9+** consigliato
- Dipendenze Python (vedi `requirements.txt`):
  - `pandas`
  - `plotly`

> Nota: il modulo (`modulo_investimento.py`) può funzionare anche **senza** `pandas`, ma in quel caso il metodo `dataframe()` non è disponibile.

## Installazione

```bash
# (opzionale) crea un virtualenv
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt

## API: `ProgettoImmobiliare`

### Parametri principali

- **`prezzo_appartamento`** *(float)*: prezzo di acquisto dell’immobile.
- **`quota_mutuo`** *(float)*: quota finanziata.
  - Valori accettati: **0–1** (es. `0.80`) **oppure** percentuale intera (es. `80` per 80%).
- **`tasso_annuo_mutuo`** *(float)*: tasso annuo del mutuo.
  - Valori accettati: decimale (es. `0.03`) **oppure** percentuale (es. `3` per 3%).
- **`affitto_mensile_stimato`** *(float)*: ricavo mensile stimato da locazione.
- **`aliquota_tasse`** *(float)*: aliquota fiscale applicata all’utile annuale.
  - Valori accettati: decimale (es. `0.21`) **oppure** percentuale (es. `21`).
- **`durata_prestito_anni`** *(int)*: durata del mutuo (anni).
- **`durata_progetto_anni`** *(int, opzionale)*: durata complessiva della simulazione (anni).
  - Se omesso, coincide con `durata_prestito_anni`.
- **`modalita_prestito`** *("rata_fissa" | "quota_capitale_fissa")*: modalità di ammortamento:
  - `rata_fissa`: rata costante (tipicamente “alla francese”).
  - `quota_capitale_fissa`: quota capitale costante, rata decrescente.
- **`pagamenti_per_anno`** *(int)*: numero di rate all’anno (default **12**).
- **`tasso_attualizzazione_annuo`** *(float)*: tasso annuo di attualizzazione per il calcolo del **VAN**.
  - Valori accettati: decimale (es. `0.10`) **oppure** percentuale (es. `10`).

### Metodi utili

- **`calcola_flussi()`** → `(cashflow_mensile, dettagli)`  
  Calcola i flussi mensili e restituisce:
  - `cashflow_mensile`: lista/array dei flussi mensili netti (incluso effetto tasse).
  - `dettagli`: dizionario con serie utili (rate, interessi, capitale, tasse, ecc.).

- **`VAN()`** → `float`  
  Calcola il **Valore Attuale Netto** scontando i flussi mensili con `tasso_attualizzazione_annuo`.

- **`riassunto()`** → `dict`  
  Restituisce un dizionario con metriche aggregate (es. equity iniziale, totali pagati, VAN, durate).

- **`dataframe()`** → `pandas.DataFrame`  
  Costruisce una tabella mensile con le principali componenti (richiede **pandas**).

## Assunzioni e note importanti

- Il cash flow operativo mensile è: **`affitto − rata`**.
- Le **tasse** vengono calcolate **a fine anno** applicando l’aliquota all’utile annuale **solo se positivo**.  
  Successivamente vengono sottratte nel mese di **dicembre** (quindi nella serie `tasse_mensili` compaiono valori **negativi** a dicembre).
- Dopo la fine del mutuo, se **`durata_progetto_anni`** è maggiore, le **rate diventano 0** e restano solo gli affitti (salvo tassazione annuale).

## Limiti del modello

Il modello è volutamente “snello”. Ad oggi non include, ad esempio:

- spese condominiali, manutenzione, assicurazioni
- vacancy / periodi di sfitto
- rivalutazione dell’immobile, vendita finale, tassazione su plusvalenza
- inflazione, adeguamento canoni, scenari e analisi di sensitività
