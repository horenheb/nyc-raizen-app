
from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta
import mysql.connector
import pandas as pd
from urllib.parse import unquote
import matplotlib.pylab as plt
import matplotlib 
matplotlib.use('Agg')
import numpy as np
import io
import base64
import sqlite3
from matplotlib.pylab import rcParams
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
from flask_cors import CORS
from furl import furl
from flask import request

rcParams['figure.figsize'] = 15, 6

app = Flask(__name__) 
CORS(app)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/nyc')
def get():



    station_name = request.args.get('station')
    date_time_str = request.args.get('date_ref')
    

    conn = sqlite3.connect("nyc-db.db")

    plt.clf()

    train_per = 0.8
    test_per = 0.2
    #date_time_str = '08-10-2010'

    

    time_interval = 100


    

    selected_date = datetime.strptime(date_time_str, '%Y-%m-%d').date()

    

    last_date =  selected_date + timedelta(days=int(time_interval*test_per))
    first_date =  selected_date - timedelta(days=int(time_interval*train_per))                                                               



    first_date = first_date.strftime("%Y-%m-%d")
    last_date = last_date.strftime("%Y-%m-%d")

    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT scp FROM nycmetrotable WHERE station = '%s'" % station_name)
    scp_distinct = cursor.fetchall()

    cursor.execute("SELECT DISTINCT linename FROM nycmetrotable WHERE station = '%s'" % station_name)
    linename_distinct = cursor.fetchall()

    firstRun=True
    for scp in scp_distinct:

        for linename in linename_distinct:

            sql = ( "SELECT Date(timestamp) As date, timestamp, scp, entries FROM nycmetrotable " 
                    "WHERE station = '%s' AND "
                    "scp = '%s' AND "
                    "linename = '%s' AND " 
                    "timestamp > '%s' AND timestamp < '%s' " 
                    "ORDER BY scp, timestamp;" %(station_name, scp[0], linename[0], first_date, last_date))
            
            df = pd.read_sql(sql, conn)
            df['shift_entries'] = df.entries.shift(1)
            df['arrival'] = df['entries'] - df['shift_entries']
            df = df.dropna(subset=["arrival"])
            df = df[(df['arrival'] >= 0)]
            
            if firstRun:
                dataset = df
                firstRun = False
            else:
                dataset = pd.concat([dataset, df])
                
            # Série temporal
            data = dataset[["date", "arrival"]]
            data["date"] = pd.to_datetime(data["date"])
            data = data.groupby(["date"]).sum()

    train_size = round(data.size*train_per)
    test_size = round(data.size*test_per)

    train = data[:train_size]
    test = data[-test_size:]

    mod = sm.tsa.statespace.SARIMAX(train, order=(0, 0, 0), seasonal_order=(0, 1, 1, 7), enforce_stationarity=False, enforce_invertibility=True)
    results = mod.fit()
    pred_uc = results.get_forecast(steps=test_size)

    # Gráfico consolidado:
    plt.clf()
    plt.title("SARIMA Model - %s" %station_name)
    plt.axvline(x=selected_date, color='red', linestyle='dotted', linewidth=5)
    plt.plot(train, label="train", linewidth=2, marker='.')
    plt.plot(test, label="test", linewidth=2, marker='.')
    plt.plot(pred_uc.predicted_mean, label="forecast", linestyle='dashed' ,linewidth=2, marker='.')
    plt.margins(.03, .2)
    plt.grid(True, linewidth=0.1, color='#ff0000', linestyle='-')
    plt.legend(loc="upper right")
    my_stringIObytes = io.BytesIO()
    plt.savefig(my_stringIObytes, format='jpeg', dpi=75)
    my_stringIObytes.seek(0)
    p_chart = base64.b64encode(my_stringIObytes.getvalue()).decode("utf-8").replace("\n", "")
    #p_chart = '<img align="left" src="data:image/jpeg;base64,%s">' % my_base64
    
    # Gráfico detalhamento:
    plt.clf()
    plt.title("Actual vs Forecast - %s" %station_name)
    plt.plot(test, label="actual", linewidth=3, marker='o')
    plt.plot(pred_uc.predicted_mean, label="forecast", linestyle='dashed' ,linewidth=3, marker='o')
    plt.margins(.03, .2)
    plt.grid(True, linewidth=0.1, color='#ff0000', linestyle='-')
    plt.legend(loc="upper right")
    my_stringIObytes = io.BytesIO()
    plt.savefig(my_stringIObytes, format='jpeg', dpi=75)
    my_stringIObytes.seek(0)
    p_chart_d = base64.b64encode(my_stringIObytes.getvalue()).decode("utf-8").replace("\n", "")
    #p_chart_d = '<img align="left" src="data:image/jpeg;base64,%s">' % my_base64



    return render_template("nyc.html", p_chart_html = p_chart , p_chart_d_html = p_chart_d)

if __name__ == '__main__':
   app.run(debug=True)

