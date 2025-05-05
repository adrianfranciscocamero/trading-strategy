import yfinance as yf
import pandas as pd
import streamlit as st
import io

# --- Diagnóstico adicional ---
if st.button("Test conexión yfinance con ES=F"):
    try:
        df_test = yf.download("ES=F", period="2d", auto_adjust=False, multi_level_index=False)
        st.write("Resultado de yf.download('ES=F'):", df_test)
    except Exception as e:
        st.error(f"❌ Error al descargar ES=F: {e}")

# --- CSS personalizado ---
st.markdown(
    """
    <style>
    input {
        border: 2px solid #4a4a4a !important;
        border-radius: 8px;
        padding: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title('Simulación de Estrategia de Trading')

# Inputs del usuario
ticker = st.text_input('Introduce el ticker del activo de Yahoo Finance')
start_date = st.date_input('Fecha de inicio')
end_date = st.date_input('Fecha final')
buy_threshold = st.number_input('Introduce el porcentaje de compra (por ejemplo, 1 para 1%):', value=0.5)
sell_threshold = st.number_input('Introduce el porcentaje de venta (por ejemplo, 1 para 1%):', value=0.5)

# Función alternativa para validar el ticker usando yf.download()
def validate_ticker(ticker):
    try:
        df = yf.download(ticker, period="2d", auto_adjust=False, multi_level_index=False)
        st.write(f"DEBUG - Validación de ticker '{ticker}':", df)
        return not df.empty and 'Close' in df.columns
    except Exception as e:
        st.error(f"⚠️ Error al validar el ticker '{ticker}': {e}")
        return False

if st.button('Ejecutar Estrategia'):

    if not validate_ticker(ticker):
        st.error(f"El ticker '{ticker}' no se encuentra en Yahoo Finance. Por favor, introduce un ticker válido.")
    else:
        # Descarga de datos
        sp = yf.download(ticker, start=start_date, end=end_date, auto_adjust=False, multi_level_index=False, progress=False)

        if end_date not in sp.index:
            sp = yf.download(ticker, start=start_date, end=pd.to_datetime(end_date) + pd.Timedelta(days=1), auto_adjust=False, multi_level_index=False, progress=False)

        if isinstance(sp.columns, pd.MultiIndex):
            sp.columns = sp.columns.droplevel(1)

        if sp.empty:
            st.error(f"No se encontraron datos para el ticker '{ticker}' entre {start_date} y {end_date}.")
        else:
            initial_investment = 100.0
            first_close_price = sp.iloc[0]['Close']
            position = initial_investment / first_close_price
            liquidity = 0.0
            buy_price = None
            sell_price = first_close_price * (1 - sell_threshold / 100)
            state = 'C'

            trade_log = []
            trade_summary = []
            previous_close = first_close_price

            for idx, (date, row) in enumerate(sp.iterrows()):
                close_price = row['Close']
                low_price = row['Low']
                high_price = row['High']
                open_price = row['Open']

                daily_variation = (close_price - previous_close) / previous_close if idx > 0 else 0
                daily_range_variation = (high_price - low_price) / low_price

                price_compra = None
                price_venta = None
                salto_orden = ""

                if idx == 0:
                    trade_log.append([date, close_price, daily_variation, low_price, high_price, daily_range_variation, open_price, state, liquidity, position * close_price, None, None, salto_orden])
                    previous_close = close_price
                    continue

                if position > 0:
                    sell_price = max(sell_price, previous_close * (1 - sell_threshold / 100))

                    if open_price < sell_price:
                        liquidity = position * open_price
                        position = 0
                        buy_price = close_price * (1 + buy_threshold / 100)
                        state = 'V'
                        price_venta = open_price
                        salto_orden = "X"
                        trade_summary.append(f"Venta realizada el {date} a {open_price} debido a salto en la orden")
                    elif low_price <= sell_price <= high_price:
                        liquidity = position * sell_price
                        position = 0
                        buy_price = close_price * (1 + buy_threshold / 100)
                        state = 'V'
                        price_venta = sell_price
                        trade_summary.append(f"Venta realizada el {date} a {sell_price}")
                else:
                    state = 'V'
                    if buy_price is None:
                        buy_price = previous_close * (1 + buy_threshold / 100)
                    else:
                        buy_price = min(buy_price, previous_close * (1 + buy_threshold / 100))

                    if open_price > buy_price:
                        position = liquidity / open_price
                        liquidity = 0
                        sell_price = close_price * (1 - sell_threshold / 100)
                        state = 'C'
                        price_compra = open_price
                        salto_orden = "X"
                        trade_summary.append(f"Compra realizada el {date} a {open_price} debido a salto en la orden")
                    elif low_price <= buy_price <= high_price:
                        position = liquidity / buy_price
                        liquidity = 0
                        sell_price = close_price * (1 - sell_threshold / 100)
                        state = 'C'
                        price_compra = buy_price
                        trade_summary.append(f"Compra realizada el {date} a {buy_price}")

                trade_log.append([date, close_price, daily_variation, low_price, high_price, daily_range_variation, open_price, state, liquidity, position * close_price, price_compra, price_venta, salto_orden])
                previous_close = close_price

            trade_df = pd.DataFrame(trade_log, columns=['Fecha', 'Cierre', 'Variación día al cierre', 'Min', 'Max', 'Variación día Min-Max', 'Apertura', 'Estado', 'Tesorería', 'Cartera', 'Precio Compra', 'Precio Venta', 'Salto en la orden'])

            final_value = trade_df.iloc[-1]['Cartera'] + trade_df.iloc[-1]['Tesorería']
            return_percentage = ((final_value - initial_investment) / initial_investment) * 100

            file_name = f'{ticker}_resultados_operativa.xlsx'
            trade_df.to_excel(file_name, index=False)

            start_simulation_date = trade_df.iloc[0]['Fecha'].strftime('%Y-%m-%d')
            end_simulation_date = trade_df.iloc[-1]['Fecha'].strftime('%Y-%m-%d')

            st.success(f"Simulación completada. El retorno final de la estrategia ({buy_threshold}, {-sell_threshold}) % para el {ticker} entre {start_simulation_date} y {end_simulation_date} es del {return_percentage:.2f}%")

            initial_close_price = sp.iloc[0]['Close']
            final_close_price = sp.iloc[-1]['Close']
            cash_return = ((final_close_price - initial_close_price) / initial_close_price) * 100

            st.info(f"El retorno al contado para el {ticker} entre {start_simulation_date} y {end_simulation_date} es del {cash_return:.2f}%")

            with open(file_name, 'rb') as file:
                st.download_button('Descargar Excel', data=file, file_name=file_name)

            summary_txt = "\n".join(trade_summary)
            summary_file_name = f'{ticker}_Resumen_Operativa.txt'

            st.download_button(
                label="Descargar Resumen de Operaciones",
                data=summary_txt,
                file_name=summary_file_name,
                mime="text/plain"
            )




