from dataclasses import dataclass, field
from typing import List, Literal, Dict, Any, Tuple, Optional
import math

try:
    import pandas as pd  # opzionale: serve solo per dataframe()
except Exception:
    pd = None

LoanMode = Literal["rata_fissa", "quota_capitale_fissa"]


def _to_decimal_rate(x: float) -> float:
    """
    Se un tasso è passato come percentuale (es. 5, 5.0, 5%),
    lo converte in decimale. Se è già decimale (es. 0.05) lo lascia invariato.
    """
    if isinstance(x, (int, float)):
        return x/100.0 if x > 1 else float(x)
    # fallback super semplice per stringhe tipo "5%" o "5"
    try:
        s = str(x).strip().replace("%", "")
        v = float(s)
        return v/100.0 if v > 1 else v
    except Exception:
        raise ValueError(f"Impossibile interpretare il tasso: {x!r}")


@dataclass
class ProgettoImmobiliare:
    # INPUT DI BASE
    prezzo_appartamento: float
    quota_mutuo: float  # percentuale dell'investimento coperta da mutuo (es. 0.8)
    tasso_annuo_mutuo: float  # in decimale (es. 0.04). Se >1, viene interpretato come %
    affitto_mensile_stimato: float
    aliquota_tasse: float  # in decimale (es. 0.26). Se >1, viene interpretato come %
    durata_prestito_anni: int
    # NUOVO: vita del progetto (può essere diversa dalla durata del finanziamento)
    durata_progetto_anni: Optional[int] = None

    # PARAMETRI TECNICI
    modalita_prestito: LoanMode = "rata_fissa"
    pagamenti_per_anno: int = 12
    tasso_attualizzazione_annuo: float = 0.0  # per VAN. In decimale; se >1, interpretato come %

    # campi calcolati
    cashflow_mensile: List[float] = field(default_factory=list)
    dettagli_prestito: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # normalizza tassi (accetta sia % che decimali)
        self.tasso_annuo_mutuo = _to_decimal_rate(self.tasso_annuo_mutuo)
        self.aliquota_tasse = _to_decimal_rate(self.aliquota_tasse)
        self.tasso_attualizzazione_annuo = _to_decimal_rate(self.tasso_attualizzazione_annuo)

        if not (0 <= self.quota_mutuo <= 1):
            # se l'utente passa 80 intende 80% → 0.8
            self.quota_mutuo = self.quota_mutuo / 100.0 if self.quota_mutuo > 1 else self.quota_mutuo

        if self.pagamenti_per_anno < 1:
            raise ValueError("pagamenti_per_anno deve essere almeno 1")

        if self.durata_progetto_anni is None:
            # compatibilità retro: se non specificato, uguale alla durata del prestito
            self.durata_progetto_anni = self.durata_prestito_anni
        if self.durata_progetto_anni < 1:
            raise ValueError("durata_progetto_anni deve essere almeno 1")

    # --- PROPRIETÀ DI COMODO ---
    @property
    def ammontare_mutuo(self) -> float:
        return self.prezzo_appartamento * self.quota_mutuo

    @property
    def equity_iniziale(self) -> float:
        return self.prezzo_appartamento * (1 - self.quota_mutuo)

    # --- CALCOLI FINANZIAMENTO ---
    def _ammortamento(self) -> Dict[str, List[float]]:
        """
        Restituisce dizionario con liste per ciascun periodo di pagamento del mutuo:
        'interesse', 'capitale', 'rata', 'residuo'.
        Periodo = 1/pagamenti_per_anno (es. mensile se 12).
        La lunghezza di queste liste è n = durata_prestito_anni * pagamenti_per_anno.
        """
        n = self.durata_prestito_anni * self.pagamenti_per_anno
        r = self.tasso_annuo_mutuo / self.pagamenti_per_anno  # tasso per periodo
        P = self.ammontare_mutuo

        interessi: List[float] = []
        capitale: List[float] = []
        rata: List[float] = []
        residuo: List[float] = []

        saldo = P

        if self.modalita_prestito == "rata_fissa":
            # rata annuità
            if r == 0:
                rata_costante = P / n
            else:
                rata_costante = P * (r * (1 + r)**n) / ((1 + r)**n - 1)

            for _ in range(n):
                interesse_k = saldo * r
                capitale_k = rata_costante - interesse_k
                saldo = max(0.0, saldo - capitale_k)

                interessi.append(interesse_k)
                capitale.append(capitale_k)
                rata.append(interesse_k + capitale_k)
                residuo.append(saldo)

        elif self.modalita_prestito == "quota_capitale_fissa":
            # quota capitale costante
            quota_capitale = P / n
            for _ in range(n):
                interesse_k = saldo * r
                pagamento_k = quota_capitale + interesse_k
                saldo = max(0.0, saldo - quota_capitale)

                interessi.append(interesse_k)
                capitale.append(quota_capitale)
                rata.append(pagamento_k)
                residuo.append(saldo)
        else:
            raise ValueError(f"Modalità prestito non riconosciuta: {self.modalita_prestito}")

        return {
            "interesse": interessi,
            "capitale": capitale,
            "rata": rata,
            "residuo": residuo,
        }

    def _mappa_rate_su_mesi(self, rate_per_periodo: List[float], project_months: int) -> List[float]:
        """
        Converte la sequenza delle rate (definite su base 'pagamenti_per_anno') in
        una sequenza mensile lungo tutta la durata del PROGETTO.
        Se il progetto dura di più del prestito, dopo l'ultima rata si hanno zeri.
        Se il progetto dura meno del prestito, le rate in eccesso vengono tagliate.
        """
        total_months_fin = self.durata_prestito_anni * 12
        pag_per_anno = self.pagamenti_per_anno
        mesi = [0.0] * project_months

        n_periodi = len(rate_per_periodo)
        for k in range(n_periodi):
            # indice mese 0-based in timeline finanziamento
            mese_fin_idx = int(math.floor((k * 12) / pag_per_anno))
            if mese_fin_idx >= total_months_fin:
                mese_fin_idx = total_months_fin - 1
            if 0 <= mese_fin_idx < project_months:
                mesi[mese_fin_idx] += rate_per_periodo[k]
        return mesi

    def _allinea_serie_ammortamento_mensile(self, serie_per_periodo: List[float], project_months: int) -> List[float]:
        """
        Allinea una qualsiasi serie del piano ammortamento (per periodo di pagamento)
        alla timeline MENSILE del progetto, come _mappa_rate_su_mesi.
        """
        return self._mappa_rate_su_mesi(serie_per_periodo, project_months)

    def _calcola_tasse_annuali(self, cf_mensili_al_lordo_tasse: List[float]) -> List[float]:
        """
        Calcola le tasse a fine anno applicando l'aliquota al reddito netto
        annuale (somma dei 12 mesi). Se negativo, tasse = 0.
        Le tasse vengono sottratte nel mese di dicembre di ciascun anno.
        La durata considerata è quella del PROGETTO.
        """
        mesi = len(cf_mensili_al_lordo_tasse)
        if mesi == 0:
            return []
        anni = (mesi + 11) // 12  # arrotonda per eccesso
        tasse_mensili = [0.0] * mesi
        for y in range(anni):
            start = y * 12
            end = min((y + 1) * 12, mesi)
            utile_anno = sum(cf_mensili_al_lordo_tasse[start:end])
            tassa_anno = max(0.0, utile_anno) * self.aliquota_tasse
            # allocazione a dicembre (mese end-1)
            tasse_mensili[end - 1] -= tassa_anno
        return tasse_mensili

    # --- FLUSSI E METRICHE ---
    def calcola_flussi(self) -> Tuple[List[float], Dict[str, Any]]:
        """
        Calcola e salva:
        - flusso di cassa mensile del progetto (incluso -equity iniziale al mese 0)
        - dettagli allineati alla frequenza mensile (affitto, rata, interessi, capitale, residuo, tasse)
        Ritorna (cashflow_mensile, dettagli).
        """
        amm = self._ammortamento()

        project_months = self.durata_progetto_anni * 12

        # Serie mensili allineate alla DURATA PROGETTO
        rate_mensili = self._mappa_rate_su_mesi(amm["rata"], project_months)
        interessi_mensili = self._allinea_serie_ammortamento_mensile(amm["interesse"], project_months)
        capitale_mensile = self._allinea_serie_ammortamento_mensile(amm["capitale"], project_months)
        # residuo è per periodo: allineiamo al mese e teniamo l'ultimo valore nel mese
        residuo_mensile = self._allinea_serie_ammortamento_mensile(amm["residuo"], project_months)

        # Affitti su tutta la vita del progetto
        affitti = [self.affitto_mensile_stimato] * project_months

        # Flusso pre-tasse: affitto - pagamento finanziamento
        cf_lordo_tasse = [affitti[i] - rate_mensili[i] for i in range(project_months)]

        # Tasse a fine anno (timeline progetto)
        tasse = self._calcola_tasse_annuali(cf_lordo_tasse)

        # Cash flow netto
        cf_netto = [cf_lordo_tasse[i] + tasse[i] for i in range(project_months)]

        # Inserisco l'esborso iniziale dell'equity al mese 0 (tempo 0)
        cf_con_equity = [-self.equity_iniziale] + cf_netto

        # Salva internamente
        self.cashflow_mensile = cf_con_equity
        self.dettagli_prestito = {
            "ammortamento_per_periodo": amm,
            "rate_mensili": rate_mensili,
            "interessi_mensili": interessi_mensili,
            "capitale_mensile": capitale_mensile,
            "residuo_mensile": residuo_mensile,
            "affitti_mensili": affitti,
            "pre_tasse_mensile": cf_lordo_tasse,
            "tasse_mensili": tasse,
            "durata_progetto_mesi": project_months,
        }
        return self.cashflow_mensile, self.dettagli_prestito

    def VAN(self) -> float:
        """
        Calcola il Valore Attuale Netto (VAN) scontando i flussi mensili
        con il tasso di attualizzazione annuo fornito.
        Considera la durata del PROGETTO.
        """
        if not self.cashflow_mensile:
            self.calcola_flussi()

        if self.tasso_attualizzazione_annuo < -0.9999:
            raise ValueError("Tasso di attualizzazione annuo non valido")

        # tasso mensile equivalente
        rm = (1 + self.tasso_attualizzazione_annuo)**(1/12) - 1

        van = 0.0
        for t, cf in enumerate(self.cashflow_mensile):
            van += cf / ((1 + rm)**t)
        return van

    def riassunto(self) -> Dict[str, Any]:
        """
        Ritorna un riassunto utile per reporting.
        """
        if not self.cashflow_mensile:
            self.calcola_flussi()

        totale_affitti = sum(self.dettagli_prestito["affitti_mensili"])
        totale_rate = sum(self.dettagli_prestito["rate_mensili"])
        totale_tasse = sum(self.dettagli_prestito["tasse_mensili"])
        van = self.VAN()

        return {
            "equity_iniziale": self.equity_iniziale,
            "totale_affitti_incassati": totale_affitti,
            "totale_rate_pagati": totale_rate,
            "totale_tasse_pagate": -totale_tasse,  # tasse_mensili sono negative nel vettore
            "VAN": van,
            "durata_progetto_mesi": self.dettagli_prestito.get("durata_progetto_mesi"),
            "durata_prestito_mesi": self.durata_prestito_anni * 12,
        }

    # --- UTILS ---
    def dataframe(self):
        """
        Restituisce (se pandas disponibile) un DataFrame mensile con:
        mese, affitto, rata, interessi, capitale, residuo, tasse, pre_tasse, cf_netto
        La riga 0 rappresenta il mese 0 con l'esborso iniziale (equity).
        """
        if pd is None:
            raise RuntimeError("pandas non disponibile nell'ambiente corrente")

        if not self.cashflow_mensile:
            self.calcola_flussi()

        det = self.dettagli_prestito
        mesi = det["durata_progetto_mesi"]
        records = []
        # mese 0: equity
        records.append({
            "mese": 0,
            "affitto": 0.0,
            "rata": 0.0,
            "interessi": 0.0,
            "capitale": 0.0,
            "residuo": self.ammontare_mutuo,
            "tasse": 0.0,
            "pre_tasse": 0.0,
            "cf_netto": -self.equity_iniziale,
        })
        for i in range(mesi):
            records.append({
                "mese": i+1,
                "affitto": det["affitti_mensili"][i],
                "rata": det["rate_mensili"][i],
                "interessi": det["interessi_mensili"][i],
                "capitale": det["capitale_mensile"][i],
                "residuo": max(0.0, det["residuo_mensile"][i]),
                "tasse": det["tasse_mensili"][i],  # negativa a dicembre
                "pre_tasse": det["pre_tasse_mensile"][i],
                "cf_netto": self.cashflow_mensile[i+1],
            })
        return pd.DataFrame.from_records(records)
