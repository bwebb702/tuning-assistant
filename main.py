import numpy as np
import pandas as pd
import plotly.graph_objects as go
from tkinter import filedialog as fd
from tkinter import Tk


headers = {
    "Time (msec)" : "Time",
    "CL/OL Fueling* (status)" : "CL/OL",
    "Engine Load* (g/rev)" : "g/rev",
    "Engine Speed (rpm)" : "RPM",
    "Feedback Knock Correction* (degrees)" : "FBKC",
    "Fine Learning Knock Correction* (degrees)" : "FLKC",
    "Fueling Final Base* (estimated AFR)" : "Est AFR",
    "Ignition Total Timing (degrees)" : "Timing",
    "Intake VVT Advance Angle Left (degrees)" : "AVCS",
    "Manifold Relative Pressure (psi)" : "MRP",
    "Mass Airflow (g/s)" : "g/s",
    "Throttle Opening Angle (%)" : "Throttle",
    "AEM UEGO Wideband [9600 baud] (AFR Gasoline)" : "WBO2",
    "Mass Airflow Sensor Voltage (V)" : "MAF Volts",
    "Intake Air Temperature (C)" : "IAT-C",
    "Intake Air Temperature (F)" : "IAT-F",
    "Coolant Temperature (C)" : "ECT-C",
    "Coolant Temperature (F)" : "ECT-F",
    "Ambient Air Temperature (C)" : "AAT-C",
    "Ambient Air Temperature (F)" : "AAT-F",
    "Exhaust Gas Temperature (C)" : "EGT-C",
    "Exhaust Gas Temperature (F)" : "EGT-F",
}


def formatTable(df):
    load_headers = list(round(df.iloc[0,], 2))
    rpm_headers = list(df.iloc[1:, 0])
    df = df.iloc[1:, 1:]

    for i, col in enumerate(df.columns):
        df = df.rename(columns={col: load_headers[i]})
    for i, n in enumerate(rpm_headers):
        df = df.rename(index={i+1: int(n)})
    return df


def getWOTruns(df):

    # df = df[df['Throttle Opening Angle (%)'] > 75]
    for key in headers:
        if key in df.columns:
            df = df.rename(columns={key: headers[key]})

    # Identify where consecutive 100s start a new group
    df['run'] = (df['Throttle'].eq(100) & ~df['Throttle'].shift().eq(100)).cumsum()

    # Only keep group numbers for rows that are 100; others = NaN
    df.loc[~df['Throttle'].eq(100), 'run'] = None
    filtered_df = df[df['run'].notna()].reset_index(drop=True)
    filtered_df['run'] = filtered_df['run'].astype(int)

    # Split into separate DataFrames
    group_dfs = [g.reset_index(drop=True) for _, g in filtered_df.groupby('run')]

    return group_dfs


def getWOTparams(df, log):
    r, g = [], []
    logged_gs = log['g/rev'].tolist()
    logged_rpm = log['RPM'].tolist()

    for grev in logged_gs:
        for g_rev in df.columns.tolist():
            if g_rev - .1 < grev <= g_rev + .1:
                g.append(g_rev)
                break
    for rpm in logged_rpm:
        for r_pm in df.index:
            if r_pm - 200 < rpm <= r_pm + 200:
                r.append(r_pm)
                break
    return g, r


def getKnocking(df, log):
    g, r = [], []
    logged_FBKC = log.loc[log['FBKC'] < 0]
    logged_FLKC = log.loc[log['FLKC'] < 0]
    if len(logged_FBKC.index) == 0 and len(logged_FLKC.index) == 0:
        return g, r
    logged_knock = pd.concat([logged_FBKC, logged_FLKC])
    for grev in logged_knock['g/rev'].tolist():
        for g_rev in df.columns.tolist():
            if g_rev - .1 < grev <= g_rev + .1:
                g.append(g_rev)
                break
    for rpm in logged_knock['RPM'].tolist():
        for r_pm in df.index:
            if r_pm - 200 < rpm <= r_pm + 200:
                r.append(r_pm)
                break
    return g, r


def getAVCS(avcs, log):
    r, g = [], []
    logged_gs = log['g/rev'].tolist()
    logged_rpm = log['RPM'].tolist()
    for grev in logged_gs:
        for g_rev in avcs.columns.tolist():
            if g_rev - .1 < grev <= g_rev + .1:
                g.append(g_rev)
                break
    for rpm in logged_rpm:
        for r_pm in avcs.index:
            if r_pm - 200 < rpm <= r_pm + 200:
                r.append(r_pm)
                break
    return g, r


def getVE(df):
    VE = []
    ATM_KPA = 92
    DISP = 128.15
    logged_RPM = df['RPM'].tolist()
    logged_gs = df['g/rev'].tolist()
    logged_MRP = df['MRP'].tolist()

    try:
        logged_IAT = df['IAT-F'].tolist()
        logged_IAT = [(x - 32) * 5/9 for x in logged_IAT]
    except KeyError:
        logged_IAT = df['IAT-C'].tolist()

    for RPM, MAF, AMP, IAT in zip(logged_RPM, logged_gs, logged_MRP, logged_IAT):
        AMP = (AMP * 6.89476) + ATM_KPA
        MAF = MAF * RPM / 60
        calc_VE = (MAF / ((AMP * 1000) / (287.05 * (IAT + 273.15)) * 1000)) / (DISP * RPM / 3456 * 0.0283 / 60)
        VE.append(round(calc_VE * 100, 3))
    df_VE = pd.DataFrame({'1': VE}, index=logged_RPM)

    return df_VE


def make_annotated_heatmap(df, title, colorscale='Spectral', xaxis_title='Load (g/rev)', not_rev=False, used=None, knock=None):
    text = np.round(df.values, 2).astype(str)
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=df.columns.astype(str),
        y=df.index.astype(str),
        text=text,
        texttemplate="%{text}",
        colorscale=colorscale,
        showscale=False
    ))

    # Highlight used (black) and knock (red) cells
    if used:
        for r, g in used:
            if (r in df.index) and (g in df.columns):
                y_i = list(df.index.astype(str)).index(str(r))
                x_i = list(df.columns.astype(str)).index(str(g))
                fig.add_shape(
                    type="rect",
                    x0=x_i - 0.5, x1=x_i + 0.5,
                    y0=y_i - 0.5, y1=y_i + 0.5,
                    line=dict(color="black", width=2),
                    fillcolor="rgba(0,0,0,0)"
                )

    if knock:
        for r, g in knock:
            if (r in df.index) and (g in df.columns):
                y_i = list(df.index.astype(str)).index(str(r))
                x_i = list(df.columns.astype(str)).index(str(g))
                fig.add_shape(
                    type="rect",
                    x0=x_i - 0.5, x1=x_i + 0.5,
                    y0=y_i - 0.5, y1=y_i + 0.5,
                    line=dict(color="red", width=3),
                    fillcolor="rgba(0,0,0,0)"
                )

    if not_rev:
        fig.update_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title="RPM",
            yaxis_autorange=not_rev,
            width=600,
            height=600,
        )
    else:
        fig.update_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title="RPM",
            yaxis_autorange='reversed',
            width=600,
            height=600,
        )

    return fig


def plotBoost(log, boost_table):
    # boost_rpm = [2600,2800,3600,4000,4400,6000,6800]
    boost = log['MRP'].tolist()
    AFR = log['WBO2'].tolist()
    est_AFR = log['Est AFR'].tolist()
    RPM = log['RPM'].tolist()
    tgt_boost = boost_table[100.00].tolist()
    peak_boost = max(boost)
    peak_rpm = RPM[boost.index(peak_boost)]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=RPM, y=boost, mode='lines', name='Boost (psi)', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=RPM, y=tgt_boost, mode='lines', name='Target Boost', line=dict(dash='dash', color='darkgreen')))
    fig.add_trace(go.Scatter(x=[peak_rpm], y=[peak_boost], mode='markers+text', text=[f'{peak_boost} psi'], textposition='top center', name='Peak Boost', marker=dict(color='red', size=10)))
    fig.add_trace(go.Scatter(x=RPM, y=AFR, mode='lines', name='Wideband AFR', yaxis='y2', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=RPM, y=est_AFR, mode='lines', name='Estimated AFR', yaxis='y2', line=dict(dash='dash', color='navy')))
    fig.add_vline(x=peak_rpm)
    fig.update_layout(
        title="Boost & AFR vs RPM",
        xaxis=dict(title="RPM"),
        yaxis=dict(title="Boost (psi)", range=[0, 21]),
        yaxis2=dict(title="AFR", overlaying='y', side='right', range=[9, 17])
    )

    return fig

def plotLoadvsRPM(log):
    fig = go.Figure()
    peak_load = max(log['g/rev'])
    peak_rpm = log['RPM'].tolist()[log['g/rev'].tolist().index(peak_load)]
    fig.add_trace(go.Scatter(line=dict(color='blue'),
        x=log['RPM'],
        y=log['g/rev'],
        mode='lines',
        name='Load vs RPM',
        # line_shape='hvh',
    ))
    fig.add_trace(go.Scatter(line=dict(color='green'),
                             x=log['RPM'],
                             y=log['AVCS'],
                             mode='lines',
                             name='AVCS vs RPM',
                             yaxis='y2'
                             # line_shape='hvh',
                             ))
    fig.add_vline(x=peak_rpm)
    fig.add_trace(
        go.Scatter(x=[peak_rpm], y=[peak_load], mode='markers+text', name='Peak Load', text=[f'{peak_load} g/rev'],
                   textposition='top center', marker=dict(color='red', size=10)))

    fig.update_layout(
        title="Load (g/rev) & AVCS vs RPM",
        xaxis=dict(title="RPM"),
        yaxis=dict(title="Engine Load (g/rev)"),
        yaxis2=dict(title="AVCS Angle", overlaying='y', side='right')
    )

    return fig


def main():
    figs = []
    rom_file = "C:/WRX/wrx_rom_tables.xlsx"

    root = Tk()
    root.withdraw()  # Hide the main tkinter window
    log_file = fd.askopenfilename(
        title="Select a RomRaider Log CSV File",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    # log_file = "C:/WRX/Logs/romraiderlog_20251022_081053_wot.csv"
    if not log_file:
        print("❌ No log file selected. Exiting.")
        return

    print(f"📁 Using log file: {log_file}")

    base_timing = formatTable(pd.read_excel(rom_file, "base timing"))
    knock_advance = formatTable(pd.read_excel(rom_file, "kca"))
    ol_fueling = formatTable(pd.read_excel(rom_file, "ol fueling"))
    boost = formatTable(pd.read_excel(rom_file, "boost"))
    avcs = formatTable(pd.read_excel(rom_file, "avcs groupn"))

    total_timing = knock_advance + base_timing
    logs = getWOTruns(pd.read_csv(log_file, low_memory=False))
    print(f"Number of runs found: {len(logs)}")

    tab_buttons_html = ""
    tab_panes_html = ""

    for i, log in enumerate(logs, 1):
        VE = getVE(log)

        # Cell highlighting
        g, r = getWOTparams(total_timing, log)
        knock_g, knock_r = getKnocking(total_timing, log)
        g_avcs, r_avcs = getAVCS(avcs, log)

        used_cells = list(zip(r, g))
        knock_cells = list(zip(knock_r, knock_g))
        avcs_cells = list(zip(r_avcs, g_avcs))

        # Build figures
        fig_boost = plotBoost(log, boost)
        fig_timing = make_annotated_heatmap(total_timing, "Total Timing Map", colorscale='Spectral_r', used=used_cells, knock=knock_cells)
        fig_fuel = make_annotated_heatmap(ol_fueling, "Open Loop Fueling Map", colorscale='Spectral', used=used_cells)
        fig_avcs = make_annotated_heatmap(avcs, "AVCS Map", colorscale='Spectral_r', used=avcs_cells)
        fig_ve = make_annotated_heatmap(VE, "Volumetric Efficiency (VE)", colorscale='Spectral_r', xaxis_title="VE (%)", not_rev=True)
        fig_load = plotLoadvsRPM(log)

        figs.extend([fig_timing, fig_fuel, fig_avcs, fig_ve, fig_boost, fig_load])

        # Convert figures to HTML snippets; include plotly.js once (first snippet)
        timing_html = fig_timing.to_html(full_html=False, include_plotlyjs='cdn' if i==1 else False)
        fuel_html = fig_fuel.to_html(full_html=False, include_plotlyjs=False)
        avcs_html = fig_avcs.to_html(full_html=False, include_plotlyjs=False)
        ve_html = fig_ve.to_html(full_html=False, include_plotlyjs=False)
        boost_html = fig_boost.to_html(full_html=False, include_plotlyjs=False)
        load_html = fig_load.to_html(full_html=False, include_plotlyjs=False)

        # Build tab button
        tab_buttons_html += f"""
            <button id="tab-btn-run{i}" onclick="openTab('run{i}')" class="{ 'active' if i==1 else '' }">
                Run {i}
            </button>
        """

        # Build tab content pane
        tab_panes_html += f"""
        <div id="pane-run{i}" class="chart-pane { 'active' if i==1 else '' }">
            <div class="grid-timing">
                <!-- Row 1 -->
                <div class="map">{timing_html}</div>
                <div class="map">{fuel_html}</div>
            
                <!-- Row 2 -->
                <div class="map">{avcs_html}</div>
                <div class="map">{ve_html}</div>
            
                <!-- Row 3 -->
                <div class="map">{boost_html}</div>
                <div class="map">{load_html}</div>
            </div>
        </div>
        """

    # Combine into final page
    page_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>WRX WOT Run Analysis</title>

      <style>
        body {{ font-family: Arial, sans-serif; margin: 12px; }}

        .tab-bar {{
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
          flex-wrap: wrap;
        }}
        .tab-bar button {{
          background: #f1f1f1;
          border: 1px solid #ccc;
          padding: 8px 12px;
          cursor: pointer;
          border-radius: 6px;
          font-weight: 600;
        }}
        .tab-bar button.active {{
          background: #2b8cff;
          color: white;
          border-color: #1976d2;
        }}

        .chart-pane {{ display: none; }}
        .chart-pane.active {{ display: block; }}

        .grid-timing {{
          display: grid;
          grid-template-columns: 1fr 1fr;
          grid-template-rows: auto auto auto;
          gap: 12px;
        }}
        .boost-full {{
          grid-column: 1 / span 2;
        }}

        .map {{
          width: 100%;
          min-width: 300px;
        }}
      </style>
    </head>

    <body>
      <h1>WRX WOT Run Analysis</h1>

      <div class="tab-bar">
        {tab_buttons_html}
      </div>

      <div class="tab-content">
        {tab_panes_html}
      </div>

      <script>
        function openTab(name) {{
          const panes = document.querySelectorAll('.chart-pane');
          const buttons = document.querySelectorAll('.tab-bar button');

          panes.forEach(p => p.classList.remove('active'));
          buttons.forEach(b => b.classList.remove('active'));

          document.getElementById('pane-' + name).classList.add('active');
          document.getElementById('tab-btn-' + name).classList.add('active');

          // resize Plotly charts on tab switch
          setTimeout(() => {{
            if (window.Plotly) {{
              document.querySelectorAll('[id^="plotly"]').forEach(gd => {{
                try {{ Plotly.Plots.resize(gd); }} catch(e){{}}
              }});
            }}
          }}, 80);
        }}
      </script>
    </body>
    </html>
    """


    # Save HTML
    out_file = "c:\\wrx\\logs\\wrx_analysis.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(page_html)

    print(f"✅ Saved WRX analysis to {out_file}")

if __name__ == "__main__":
    main()
