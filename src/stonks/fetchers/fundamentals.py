"""Fetcher de fundamentales (income, balance, CF)
via yfinance."""

import yfinance as yf

import stonks.models  # noqa: F401
from stonks.db import get_session
from stonks.fetchers.base import BaseFetcher, logger
from stonks.models.equity import (
    BalanceSheet,
    CashFlow,
    Company,
    Dividend,
    IncomeStatement,
    Split,
)
from stonks.models.meta import DataSource


class FundamentalsFetcher(BaseFetcher):
    """Descarga fundamentales desde yfinance."""

    SOURCE_NAME = "yfinance"
    DOMAIN = "equity"
    RATE_LIMIT = 1.0

    @staticmethod
    def _volcar(session, exists, modelo, clave, valores, stats) -> None:
        """Insertar la fila, o actualizarla si ya estaba.

        Antes habia un `continue` aqui: una vez cargado un periodo, no
        se volvia a tocar nunca. Eso deja congelado cualquier dato que
        la fuente revise despues, y con los splits pasa siempre —el
        BPA de todo el historico cambia—. Booking figuraba con un BPA
        de 165,57 cuando Yahoo ya daba 6,62 tras el split, y de ahi
        salia un PER de 1,25 en un valor que cotiza a 31 veces
        beneficios.

        Es el tercer sitio donde aparecia el mismo patron, despues de
        `coingecko.py` y `funds.py`.
        """
        if exists is None:
            session.add(modelo(**clave, **valores))
            stats["inserted"] += 1
            return

        cambios = []
        for campo, valor in valores.items():
            if valor is None:
                # Que la fuente deje de dar un campo no es motivo para
                # borrar el que ya se tenia.
                continue
            actual = getattr(exists, campo)
            if isinstance(valor, (int, float)):
                # Los importes llegan como Decimal desde la base y como
                # float desde yfinance; hay que comparar en float.
                distinto = actual is None or float(actual) != float(valor)
            else:
                distinto = actual != valor
            if distinto:
                cambios.append(campo)

        if not cambios:
            return
        for campo in cambios:
            setattr(exists, campo, valores[campo])
        stats["updated"] += 1

    @staticmethod
    def _moneda_de_las_cuentas(t) -> str | None:
        """Moneda en la que la empresa presenta sus estados.

        Yahoo la da en `financialCurrency`, distinta de `currency`, que
        es la de cotizacion. Devuelve None si no la da: preferible no
        saber la unidad a declarar una equivocada, porque un ratio con
        dos monedas mezcladas parece un chollo y no lo es.
        """
        try:
            info = t.info or {}
        except Exception:  # noqa: BLE001
            return None
        moneda = info.get("financialCurrency")
        return str(moneda)[:3] if moneda else None

    def fetch_financials(self, ticker: str) -> dict[str, int]:
        """Descargar income, balance, cashflow."""
        run_id = self._start_run(
            params={
                "ticker": ticker,
                "type": "financials",
            }
        )
        stats = {
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
        }
        session = get_session()

        try:
            src = (
                session.query(DataSource)
                .filter_by(name=self.SOURCE_NAME)
                .first()
            )
            src_id = src.id if src else None

            comp = session.query(Company).filter_by(ticker=ticker).first()
            if not comp:
                logger.warning("Empresa %s no existe", ticker)
                self._finish_run(run_id, "failed")
                session.close()
                return stats

            t = yf.Ticker(ticker)

            # La moneda de los estados financieros NO es la de
            # cotizacion. Central Puerto cotiza en dolares y reporta en
            # pesos; Novo Nordisk cotiza en dolares su ADR y reporta en
            # coronas. Etiquetar las cuentas con `comp.currency_code`
            # —que es lo que se hacia— convertia el PER en un numero
            # sin sentido: precio en una moneda dividido entre un
            # beneficio por accion en otra. Novo Nordisk salia con PER
            # 2,0 en su ADR y 12,7 en Copenhague, con el mismo BPA.
            moneda_cuentas = self._moneda_de_las_cuentas(t)

            # Income Statement (anual)
            inc = t.income_stmt
            if inc is not None and not inc.empty:
                for col in inc.columns:
                    year = col.year
                    stats["fetched"] += 1
                    exists = (
                        session.query(IncomeStatement)
                        .filter_by(
                            company_id=comp.id,
                            fiscal_year=year,
                            fiscal_quarter=None,
                        )
                        .first()
                    )

                    def g(key):
                        try:
                            v = inc.at[key, col]
                            if v != v:  # NaN
                                return None
                            return float(v)
                        except (KeyError, TypeError):
                            return None

                    self._volcar(
                        session,
                        exists,
                        IncomeStatement,
                        {
                            "company_id": comp.id,
                            "fiscal_year": year,
                            "fiscal_quarter": None,
                        },
                        {
                            "period_end_date": col.date(),
                            "currency_code": moneda_cuentas,
                            "revenue": g("Total Revenue"),
                            "cost_of_revenue": g("Cost Of Revenue"),
                            "gross_profit": g("Gross Profit"),
                            "operating_expenses": g("Operating Expense"),
                            "operating_income": g("Operating Income"),
                            "interest_expense": g("Interest Expense"),
                            "pretax_income": g("Pretax Income"),
                            "income_tax": g("Tax Provision"),
                            "net_income": g("Net Income"),
                            "eps_basic": g("Basic EPS"),
                            "eps_diluted": g("Diluted EPS"),
                            "ebitda": g("EBITDA"),
                            "source_id": src_id,
                        },
                        stats,
                    )

            # Balance Sheet (anual)
            bal = t.balance_sheet
            if bal is not None and not bal.empty:
                for col in bal.columns:
                    year = col.year
                    stats["fetched"] += 1
                    exists = (
                        session.query(BalanceSheet)
                        .filter_by(
                            company_id=comp.id,
                            fiscal_year=year,
                            fiscal_quarter=None,
                        )
                        .first()
                    )

                    def gb(key):
                        try:
                            v = bal.at[key, col]
                            if v != v:
                                return None
                            return float(v)
                        except (KeyError, TypeError):
                            return None

                    self._volcar(
                        session,
                        exists,
                        BalanceSheet,
                        {
                            "company_id": comp.id,
                            "fiscal_year": year,
                            "fiscal_quarter": None,
                        },
                        {
                            "period_end_date": col.date(),
                            "currency_code": moneda_cuentas,
                            "cash_and_equivalents": gb(
                                "Cash And Cash Equivalents"
                            ),
                            "total_current_assets": gb("Current Assets"),
                            "property_plant_equipment": gb("Net PPE"),
                            "goodwill": gb("Goodwill"),
                            "intangible_assets": gb("Other Intangible Assets"),
                            "total_assets": gb("Total Assets"),
                            "accounts_payable": gb("Accounts Payable"),
                            "short_term_debt": gb("Current Debt"),
                            "total_current_liabilities": gb(
                                "Current Liabilities"
                            ),
                            "long_term_debt": gb("Long Term Debt"),
                            "total_liabilities": gb(
                                "Total Liabilities Net Minority Interest"
                            ),
                            "total_stockholders_equity": gb(
                                "Stockholders Equity"
                            ),
                            "retained_earnings": gb("Retained Earnings"),
                            "total_equity": gb(
                                "Total Equity Gross Minority Interest"
                            ),
                            "source_id": src_id,
                        },
                        stats,
                    )

            # Cash Flow (anual)
            cf = t.cashflow
            if cf is not None and not cf.empty:
                for col in cf.columns:
                    year = col.year
                    stats["fetched"] += 1
                    exists = (
                        session.query(CashFlow)
                        .filter_by(
                            company_id=comp.id,
                            fiscal_year=year,
                            fiscal_quarter=None,
                        )
                        .first()
                    )

                    def gc(key):
                        try:
                            v = cf.at[key, col]
                            if v != v:
                                return None
                            return float(v)
                        except (KeyError, TypeError):
                            return None

                    self._volcar(
                        session,
                        exists,
                        CashFlow,
                        {
                            "company_id": comp.id,
                            "fiscal_year": year,
                            "fiscal_quarter": None,
                        },
                        {
                            "period_end_date": col.date(),
                            "currency_code": moneda_cuentas,
                            "operating_cash_flow": gc("Operating Cash Flow"),
                            "capital_expenditure": gc("Capital Expenditure"),
                            "free_cash_flow": gc("Free Cash Flow"),
                            "dividends_paid": gc(
                                "Common Stock Dividend Paid"
                            ),
                            "share_buyback": gc(
                                "Repurchase Of Capital Stock"
                            ),
                            "debt_issued": gc("Long Term Debt Issuance"),
                            "debt_repaid": gc("Long Term Debt Payments"),
                            "investing_cash_flow": gc("Investing Cash Flow"),
                            "financing_cash_flow": gc("Financing Cash Flow"),
                            "net_change_cash": gc("Changes In Cash"),
                            "source_id": src_id,
                        },
                        stats,
                    )

            session.commit()
            self._finish_run(run_id, "success", **stats)
        except Exception as e:
            session.rollback()
            stats["errors"] += 1
            logger.error(
                "Error fundamentales %s: %s",
                ticker,
                e,
            )
            self._finish_run(
                run_id,
                "failed",
                **stats,
                error_log={"msg": str(e)},
            )
        finally:
            session.close()

        return stats

    def fetch_dividends(self, ticker: str) -> dict[str, int]:
        """Descargar historial de dividendos."""
        stats = {"fetched": 0, "inserted": 0}
        session = get_session()

        try:
            comp = session.query(Company).filter_by(ticker=ticker).first()
            if not comp:
                session.close()
                return stats

            t = yf.Ticker(ticker)
            divs = t.dividends

            if divs is None or divs.empty:
                session.close()
                return stats

            for dt_idx, amount in divs.items():
                ex_date = dt_idx.date()
                stats["fetched"] += 1
                exists = (
                    session.query(Dividend)
                    .filter_by(
                        company_id=comp.id,
                        ex_date=ex_date,
                        dividend_type="regular",
                    )
                    .first()
                )
                if exists:
                    continue
                session.add(
                    Dividend(
                        company_id=comp.id,
                        ex_date=ex_date,
                        amount=float(amount),
                        # Aqui si es la de cotizacion: yfinance da el
                        # dividendo en la misma moneda que el precio,
                        # no en la de los estados financieros.
                        currency_code=comp.currency_code,
                        dividend_type="regular",
                    )
                )
                stats["inserted"] += 1

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error dividendos %s: %s", ticker, e)
        finally:
            session.close()
        return stats

    def fetch_splits(self, ticker: str) -> dict[str, int]:
        """Descargar historial de splits."""
        stats = {"fetched": 0, "inserted": 0}
        session = get_session()

        try:
            comp = session.query(Company).filter_by(ticker=ticker).first()
            if not comp:
                session.close()
                return stats

            t = yf.Ticker(ticker)
            splits = t.splits

            if splits is None or splits.empty:
                session.close()
                return stats

            for dt_idx, ratio in splits.items():
                split_date = dt_idx.date()
                stats["fetched"] += 1
                exists = (
                    session.query(Split)
                    .filter_by(
                        company_id=comp.id,
                        date=split_date,
                    )
                    .first()
                )
                if exists:
                    continue
                session.add(
                    Split(
                        company_id=comp.id,
                        date=split_date,
                        ratio_from=1.0,
                        ratio_to=float(ratio),
                    )
                )
                stats["inserted"] += 1

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error splits %s: %s", ticker, e)
        finally:
            session.close()
        return stats

    def fetch_all_for_company(self, ticker: str) -> dict[str, dict]:
        """Descargar todo para una empresa."""
        results = {}
        results["financials"] = self.fetch_financials(ticker)
        results["dividends"] = self.fetch_dividends(ticker)
        results["splits"] = self.fetch_splits(ticker)
        return results

    def fetch_batch(self, tickers: list[str] | None = None) -> dict[str, dict]:
        """Descargar fundamentales para múltiples
        empresas."""
        if tickers is None:
            session = get_session()
            companies = (
                session.query(Company.ticker).filter_by(is_active=True).all()
            )
            tickers = [c.ticker for c in companies]
            session.close()

        results = {}
        total = len(tickers)
        for i, ticker in enumerate(tickers, 1):
            logger.info(
                "[%d/%d] Fundamentales %s...",
                i,
                total,
                ticker,
            )
            results[ticker] = self.fetch_all_for_company(ticker)
        return results
