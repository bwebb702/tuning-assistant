import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from tkinter import filedialog as fd
from tkinter import Tk
from plotly.subplots import make_subplots
from plotly.colors import sample_colorscale


# ---------- Dark Theme ----------
DARK_BG = "#181a1f"
DARK_PANEL = "#20232a"
DARK_GRID = "#3a3d45"
LIGHT_TEXT = "#e6e6e6"
MUTED_TEXT = "#a9adb7"
ACCENT = "#2b8cff"


# ---------- Column Headers ----------
headers = {
    "Time (msec)": "Time",
    "CL/OL Fueling* (status)": "CL/OL",
    "Engine Load* (g/rev)": "g/rev",
    "Engine Speed (rpm)": "RPM",
    "Feedback Knock Correction* (degrees)": "FBKC",
    "Fine Learning Knock Correction* (degrees)": "FLKC",
    "Fueling Final Base* (estimated AFR)": "Est AFR",
    "Ignition Total Timing (degrees)": "Timing",
    "Intake VVT Advance Angle Left (degrees)": "AVCS",
    "Manifold Relative Pressure (psi)": "MRP",
    "Mass Airflow (g/s)": "g/s",
    "Throttle Opening Angle (%)": "Throttle",
    "AEM UEGO Wideband [9600 baud] (AFR Gasoline)": "WBO2",
    "Mass Airflow Sensor Voltage (V)": "MAF Volts",
    "Intake Air Temperature (C)": "IAT-C",
    "Intake Air Temperature (F)": "IAT-F",
    "Coolant Temperature (C)": "ECT-C",
    "Coolant Temperature (F)": "ECT-F",
    "Ambient Air Temperature (C)": "AAT-C",
    "Ambient Air Temperature (F)": "AAT-F",
    "Exhaust Gas Temperature (C)": "EGT-C",
    "Exhaust Gas Temperature (F)": "EGT-F",
}


# ---------- Data Formatting ----------
def formatTable(df):
    load_headers = list(round(df.iloc[0,], 2))
    rpm_headers = list(df.iloc[1:, 0])
    df = df.iloc[1:, 1:]

    for i, col in enumerate(df.columns):
        df = df.rename(columns={col: load_headers[i]})

    for i, n in enumerate(rpm_headers):
        df = df.rename(index={i + 1: int(n)})

    return df


# ---------- Get WOT Runs ----------
def getWOTruns(df):

    for key in headers:
        if key in df.columns:
            df = df.rename(columns={key: headers[key]})

    df["Throttle"] = pd.to_numeric(df["Throttle"], errors="coerce")
    df["RPM"] = pd.to_numeric(df["RPM"], errors="coerce")

    df["run"] = (
        df["Throttle"].eq(100) &
        ~df["Throttle"].shift().eq(100)
    ).cumsum()

    df.loc[~df["Throttle"].eq(100), "run"] = None

    filtered_df = df[df["run"].notna()].reset_index(drop=True)

    if filtered_df.empty:
        return []

    filtered_df["run"] = filtered_df["run"].astype(int)

    group_dfs = []

    for _, group in filtered_df.groupby("run"):

        group = group.reset_index(drop=True)

        group["RPM"] = pd.to_numeric(
            group["RPM"],
            errors="coerce"
        )

        group = group[group["RPM"].notna()].reset_index(drop=True)

        if group.empty:
            continue

        min_rpm_index = group["RPM"].idxmin()

        group = group.loc[
            min_rpm_index:
        ].reset_index(drop=True)

        group_dfs.append(group)

    return group_dfs


# ---------- WOT Cell Calculations ----------
def getWOTparams(df, log):

    r, g = [], []

    logged_gs = log["g/rev"].tolist()
    logged_rpm = log["RPM"].tolist()

    for grev in logged_gs:

        for g_rev in df.columns.tolist():

            if g_rev - 0.1 < grev <= g_rev + 0.1:
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

    logged_FBKC = log.loc[log["FBKC"] < 0]
    logged_FLKC = log.loc[log["FLKC"] < 0]

    if len(logged_FBKC.index) == 0 and len(logged_FLKC.index) == 0:
        return g, r

    logged_knock = pd.concat([
        logged_FBKC,
        logged_FLKC
    ])

    for grev in logged_knock["g/rev"].tolist():

        for g_rev in df.columns.tolist():

            if g_rev - 0.1 < grev <= g_rev + 0.1:
                g.append(g_rev)
                break

    for rpm in logged_knock["RPM"].tolist():

        for r_pm in df.index:

            if r_pm - 200 < rpm <= r_pm + 200:
                r.append(r_pm)
                break

    return g, r


def getAVCS(avcs, log):

    r, g = [], []

    logged_gs = log["g/rev"].tolist()
    logged_rpm = log["RPM"].tolist()

    for grev in logged_gs:

        for g_rev in avcs.columns.tolist():

            if g_rev - 0.1 < grev <= g_rev + 0.1:
                g.append(g_rev)
                break

    for rpm in logged_rpm:

        for r_pm in avcs.index:

            if r_pm - 200 < rpm <= r_pm + 200:
                r.append(r_pm)
                break

    return g, r


# ---------- VE Calculation ----------
def getVE(df):

    VE = []

    ATM_KPA = 92
    DISP = 128.15

    logged_RPM = df["RPM"].tolist()
    logged_gs = df["g/rev"].tolist()
    logged_MRP = df["MRP"].tolist()

    try:

        logged_IAT = df["IAT-F"].tolist()

        logged_IAT = [
            (x - 32) * 5 / 9
            for x in logged_IAT
        ]

    except KeyError:

        logged_IAT = df["IAT-C"].tolist()

    for RPM, MAF, AMP, IAT in zip(
        logged_RPM,
        logged_gs,
        logged_MRP,
        logged_IAT
    ):

        AMP = (AMP * 6.89476) + ATM_KPA
        MAF = MAF * RPM / 60

        calc_VE = (
            MAF /
            (
                (AMP * 1000) /
                (
                    287.05 *
                    (IAT + 273.15)
                ) * 1000
            )
        ) / (
            DISP *
            RPM /
            3456 *
            0.0283 /
            60
        )

        VE.append(
            round(
                calc_VE * 100,
                3
            )
        )

    df_VE = pd.DataFrame(
        {"VE": VE},
        index=logged_RPM
    )

    df_VE = df_VE.sort_index()

    return df_VE




def make_annotated_heatmap(
        df,
        title,
        colorscale="Spectral",
        used=None,
        knock=None,
        x_title="Load (g/rev)",
        y_title="RPM"
):
    text = np.round(
        df.values,
        2
    ).astype(str)

    fig = go.Figure(
        data=go.Heatmap(
            z=df.values,
            x=df.columns.astype(str),
            y=df.index.astype(str),
            text=text,
            texttemplate="%{text}",
            colorscale=colorscale,
            showscale=False
        )
    )

    # ---------- Highlight Used Cells ----------
    if used:

        for r, g in used:

            if (
                    r in df.index and
                    g in df.columns
            ):
                y_i = list(
                    df.index.astype(str)
                ).index(str(r))

                x_i = list(
                    df.columns.astype(str)
                ).index(str(g))

                fig.add_shape(
                    type="rect",
                    x0=x_i - 0.5,
                    x1=x_i + 0.5,
                    y0=y_i - 0.5,
                    y1=y_i + 0.5,
                    line=dict(
                        color="black",
                        width=2
                    ),
                    fillcolor="rgba(0,0,0,0)"
                )

    # ---------- Highlight Knock Cells ----------
    if knock:

        for r, g in knock:

            if (
                    r in df.index and
                    g in df.columns
            ):
                y_i = list(
                    df.index.astype(str)
                ).index(str(r))

                x_i = list(
                    df.columns.astype(str)
                ).index(str(g))

                fig.add_shape(
                    type="rect",
                    x0=x_i - 0.5,
                    x1=x_i + 0.5,
                    y0=y_i - 0.5,
                    y1=y_i + 0.5,
                    line=dict(
                        color="red",
                        width=3
                    ),
                    fillcolor="rgba(0,0,0,0)"
                )

    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        yaxis_autorange="reversed",
        width=600,
        height=600,
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_PANEL,
        font=dict(
            color=LIGHT_TEXT
        ),
        margin=dict(
            l=70,
            r=30,
            t=60,
            b=60
        )
    )

    # ---------- Axes ----------
    fig.update_xaxes(
        gridcolor=DARK_GRID,
        linecolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        tickfont=dict(
            color=LIGHT_TEXT
        ),
        title_font=dict(
            color=LIGHT_TEXT
        )
    )

    fig.update_yaxes(
        gridcolor=DARK_GRID,
        linecolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        tickfont=dict(
            color=LIGHT_TEXT
        ),
        title_font=dict(
            color=LIGHT_TEXT
        )
    )

    return fig



# ---------- Boost / Load / AFR ----------
def plotBoost(log):

    RPM = pd.to_numeric(
        log["RPM"],
        errors="coerce"
    )

    boost = pd.to_numeric(
        log["MRP"],
        errors="coerce"
    )

    load = pd.to_numeric(
        log["g/rev"],
        errors="coerce"
    )

    wideband = pd.to_numeric(
        log["WBO2"],
        errors="coerce"
    )

    final_afr = pd.to_numeric(
        log["Est AFR"],
        errors="coerce"
    )

    valid_boost = RPM.notna() & boost.notna()
    valid_load = RPM.notna() & load.notna()
    valid_wideband = RPM.notna() & wideband.notna()
    valid_final = RPM.notna() & final_afr.notna()

    peak_boost = boost[valid_boost].max()
    peak_boost_idx = boost[valid_boost].idxmax()
    peak_boost_rpm = RPM.loc[peak_boost_idx]

    peak_load = load[valid_load].max()
    peak_load_idx = load[valid_load].idxmax()
    peak_load_rpm = RPM.loc[peak_load_idx]

    # ---------- Subplots ----------
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.67, 0.33],
        specs=[
            [{"secondary_y": True}],
            [{"secondary_y": False}]
        ]
    )

    # ---------- Engine Load ----------
    fig.add_trace(
        go.Scatter(
            x=RPM[valid_load],
            y=load[valid_load],
            mode="lines",
            name="Engine Load",
            line=dict(
                color="green"
            )
        ),
        row=1,
        col=1,
        secondary_y=False
    )

    # ---------- Boost ----------
    fig.add_trace(
        go.Scatter(
            x=RPM[valid_boost],
            y=boost[valid_boost],
            mode="lines",
            name="Boost",
            line=dict(
                color="royalblue"
            )
        ),
        row=1,
        col=1,
        secondary_y=True
    )

    # ---------- Peak Boost Marker ----------
    fig.add_trace(
        go.Scatter(
            x=[peak_boost_rpm],
            y=[peak_boost],
            mode="markers",
            name="Peak Boost",
            marker=dict(
                size=10,
                color="red"
            )
        ),
        row=1,
        col=1,
        secondary_y=True
    )

    # ---------- Peak Load Marker ----------
    fig.add_trace(
        go.Scatter(
            x=[peak_load_rpm],
            y=[peak_load],
            mode="markers",
            name="Peak Load",
            marker=dict(
                size=10,
                color="orange"
            )
        ),
        row=1,
        col=1,
        secondary_y=False
    )

    # ---------- Peak Boost Text ----------
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.005,
        y=0.995,
        xanchor="left",
        yanchor="top",
        text=(
            f"<b>Peak Boost:</b> "
            f"{peak_boost:.1f} psi "
            f"@ {peak_boost_rpm:.0f} RPM"
        ),
        showarrow=False,
        font=dict(
            color=LIGHT_TEXT
        ),
        bgcolor=DARK_PANEL,
        borderwidth=0
    )

    # ---------- Peak Load Text ----------
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0.005,
        y=0.970,
        xanchor="left",
        yanchor="top",
        text=(
            f"<b>Peak Load:</b> "
            f"{peak_load:.2f} g/rev "
            f"@ {peak_load_rpm:.0f} RPM"
        ),
        showarrow=False,
        font=dict(
            color=LIGHT_TEXT
        ),
        bgcolor=DARK_PANEL,
        borderwidth=0
    )

    # ---------- Wideband AFR ----------
    fig.add_trace(
        go.Scatter(
            x=RPM[valid_wideband],
            y=wideband[valid_wideband],
            mode="lines",
            name="Wideband AFR",
            showlegend=False,
            line=dict(
                color="firebrick"
            )
        ),
        row=2,
        col=1
    )

    # ---------- Final Fueling Base ----------
    fig.add_trace(
        go.Scatter(
            x=RPM[valid_final],
            y=final_afr[valid_final],
            mode="lines",
            name="Final Fueling Base",
            showlegend=False,
            line=dict(
                color="firebrick",
                dash="dash"
            )
        ),
        row=2,
        col=1
    )

    # ---------- Engine Load Axis ----------
    fig.update_yaxes(
        title_text="Engine Load (g/rev)",
        range=[min(load), max(load)+.2],
        row=1,
        col=1,
        secondary_y=False,
        gridcolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        linecolor=DARK_GRID
    )

    # ---------- Boost Axis ----------
    fig.update_yaxes(
        title_text="Boost (psi)",
        range=[min(boost), max(boost)+1],
        row=1,
        col=1,
        secondary_y=True,
        gridcolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        linecolor=DARK_GRID
    )

    # ---------- AFR Axis ----------
    fig.update_yaxes(
        title_text="AFR",
        range=[10, 18],
        fixedrange=True,
        row=2,
        col=1,
        gridcolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        linecolor=DARK_GRID
    )

    # ---------- Shared RPM Axis ----------
    fig.update_xaxes(
        title_text="RPM",
        gridcolor=DARK_GRID,
        zerolinecolor=DARK_GRID,
        linecolor=DARK_GRID
    )

    # ---------- Layout ----------
    fig.update_layout(
        title=dict(
            text="Boost / Load & AFR vs RPM",
            font=dict(
                color=LIGHT_TEXT
            )
        ),
        width=1000,
        height=800,
        margin=dict(
            l=80,
            r=230,
            t=70,
            b=60
        ),
        paper_bgcolor=DARK_BG,
        plot_bgcolor=DARK_PANEL,
        font=dict(
            color=LIGHT_TEXT
        ),
        legend=dict(
            x=1.02,
            y=0.98,
            xanchor="left",
            yanchor="top",
            bgcolor=DARK_PANEL,
            bordercolor=DARK_GRID,
            borderwidth=1,
            font=dict(
                color=LIGHT_TEXT
            )
        )
    )

    # ---------- Separate AFR Legend ----------
    fig.add_annotation(
        xref="paper",
        yref="paper",
        x=1.02,
        y=0.30,
        xanchor="left",
        yanchor="top",
        align="left",
        text=(
            "<span style='color:#ff0000'>━━</span> "
            "Wideband AFR<br>"
            "<span style='color:#ff0000'>┅┅</span> "
            "Final Fueling Base"
        ),
        showarrow=False,
        font=dict(
            color=LIGHT_TEXT
        ),
        bgcolor=DARK_PANEL,
        bordercolor=DARK_GRID,
        borderwidth=1
    )

    return fig


# ---------- Main ----------
def main():

    figs = []

    rom_file = "C:/WRX/wrx_rom_tables.xlsx"

    # ---------- Select Log File ----------
    root = Tk()
    root.withdraw()

    log_file = fd.askopenfilename(
        title="Select a RomRaider Log CSV File",
        filetypes=[
            ("CSV Files", "*.csv"),
            ("All Files", "*.*")
        ]
    )

    root.destroy()

    if not log_file:

        print(
            "No log file selected. Exiting."
        )

        return

    print(
        f"Using log file: {log_file}"
    )

    # ---------- ROM Tables ----------
    base_timing = formatTable(
        pd.read_excel(
            rom_file,
            "base timing"
        )
    )

    knock_advance = formatTable(
        pd.read_excel(
            rom_file,
            "kca"
        )
    )

    ol_fueling = formatTable(
        pd.read_excel(
            rom_file,
            "ol fueling"
        )
    )

    avcs = formatTable(
        pd.read_excel(
            rom_file,
            "avcs"
        )
    )

    total_timing = (
        knock_advance +
        base_timing
    )

    # ---------- Load WOT Runs ----------
    logs = getWOTruns(
        pd.read_csv(
            log_file,
            low_memory=False
        )
    )

    print(
        f"Number of runs found: "
        f"{len(logs)}"
    )

    # ---------- Process Each WOT Run ----------
    for i, log in enumerate(
        logs,
        1
    ):

        VE = getVE(log)

        g, r = getWOTparams(
            total_timing,
            log
        )

        knock_g, knock_r = getKnocking(
            total_timing,
            log
        )

        g_avcs, r_avcs = getAVCS(
            avcs,
            log
        )

        used_cells = list(
            zip(r, g)
        )

        knock_cells = list(
            zip(
                knock_r,
                knock_g
            )
        )

        avcs_cells = list(
            zip(
                r_avcs,
                g_avcs
            )
        )

        # ---------- Timing ----------
        fig_timing = make_annotated_heatmap(
            total_timing,
            "Total Timing Map",
            colorscale="Spectral_r",
            used=used_cells,
            knock=knock_cells
        )

        # ---------- Fuel ----------
        fig_fuel = make_annotated_heatmap(
            ol_fueling,
            "Open Loop Fueling Map",
            colorscale="Spectral",
            used=used_cells
        )

        fig_fuel.update_xaxes(
            tickangle=0
        )

        # ---------- AVCS ----------
        fig_avcs = make_annotated_heatmap(
            avcs,
            "AVCS Map",
            colorscale="Spectral_r",
            used=avcs_cells
        )

        # ---------- VE ----------
        fig_ve = make_annotated_heatmap(
            VE,
            "Volumetric Efficiency (VE)",
            colorscale="Spectral_r",
            x_title="VE (%)",
            y_title="RPM"
        )

        # ---------- Boost / AFR ----------
        fig_boost = plotBoost(log)

        figs.extend([
            fig_timing,
            fig_fuel,
            fig_avcs,
            fig_ve,
            fig_boost
        ])

    # ---------- Build Tabs ----------
    tab_buttons_html = ""
    tab_panes_html = ""

    for idx in range(
        len(logs)
    ):

        run_num = idx + 1
        fig_index = idx * 5

        timing_html = figs[
            fig_index
        ].to_html(
            full_html=False,
            include_plotlyjs=(
                "cdn"
                if idx == 0
                else False
            )
        )

        fuel_html = figs[
            fig_index + 1
        ].to_html(
            full_html=False,
            include_plotlyjs=False
        )

        avcs_html = figs[
            fig_index + 2
        ].to_html(
            full_html=False,
            include_plotlyjs=False
        )

        ve_html = figs[
            fig_index + 3
        ].to_html(
            full_html=False,
            include_plotlyjs=False
        )

        boost_html = figs[
            fig_index + 4
        ].to_html(
            full_html=False,
            include_plotlyjs=False
        )

        active = (
            "active"
            if run_num == 1
            else ""
        )

        # ---------- Tab Button ----------
        tab_buttons_html += f"""
        <button
            id="tab-btn-run{run_num}"
            onclick="openTab('run{run_num}')"
            class="{active}">
            Run {run_num}
        </button>
        """

        # ---------- Tab Content ----------
        tab_panes_html += f"""
        <div
            id="pane-run{run_num}"
            class="chart-pane {active}">

            <div class="grid-timing">

                <div class="map">
                    {timing_html}
                </div>

                <div class="map">
                    {fuel_html}
                </div>

                <div class="map">
                    {avcs_html}
                </div>

                <div class="map">
                    {ve_html}
                </div>

                <div class="map boost-full">
                    {boost_html}
                </div>

            </div>

        </div>
        """

    # ---------- Complete HTML ----------
    page_html = f"""
<!DOCTYPE html>

<html lang="en">

<head>

    <meta charset="utf-8"/>

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"/>

    <title>
        WRX WOT Run Analysis
    </title>

    <style>

        * {{
            box-sizing: border-box;
        }}

        html {{
            background: {DARK_BG};
        }}

        body {{
            font-family: Arial, sans-serif;
            margin: 12px;
            background: {DARK_BG};
            color: {LIGHT_TEXT};
        }}

        h1 {{
            margin-bottom: 12px;
            font-size: 20px;
            color: {LIGHT_TEXT};
        }}

        .tab-bar {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}

        .tab-bar button {{
            background: {DARK_PANEL};
            color: {MUTED_TEXT};
            border: 1px solid {DARK_GRID};
            padding: 8px 14px;
            cursor: pointer;
            border-radius: 6px;
            font-weight: 600;
            transition:
                background 0.15s,
                color 0.15s,
                border-color 0.15s;
        }}

        .tab-bar button:hover {{
            background: #292d35;
            color: {LIGHT_TEXT};
            border-color: #555b68;
        }}

        .tab-bar button.active {{
            background: {ACCENT};
            color: white;
            border-color: {ACCENT};
        }}

        .chart-pane {{
            display: none;
        }}

        .chart-pane.active {{
            display: block;
        }}

        .grid-timing {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows:
                auto
                auto
                auto;
            gap: 12px;
            width: 100%;
        }}

        .map {{
            width: 100%;
            min-width: 300px;
            background: {DARK_BG};
            border-radius: 6px;
        }}

        .boost-full {{
            grid-column: 1 / span 2;
            display: flex;
            justify-content: center;
        }}

        .boost-full
        .plotly-graph-div {{
            margin-left: auto !important;
            margin-right: auto !important;
        }}

        @media (max-width: 1100px) {{

            .grid-timing {{
                grid-template-columns: 1fr;
            }}

            .boost-full {{
                grid-column: 1;
            }}

        }}

    </style>

</head>

<body>

    <h1>
        WRX WOT Run Analysis
    </h1>

    <div class="tab-bar">

        {tab_buttons_html}

    </div>

    <div class="tab-content">

        {tab_panes_html}

    </div>


    <script>

        function openTab(name) {{

            const panes =
                document.querySelectorAll(
                    ".chart-pane"
                );

            const buttons =
                document.querySelectorAll(
                    ".tab-bar button"
                );

            panes.forEach(
                pane => {{
                    pane.classList.remove(
                        "active"
                    );
                }}
            );

            buttons.forEach(
                button => {{
                    button.classList.remove(
                        "active"
                    );
                }}
            );

            document
                .getElementById(
                    "pane-" + name
                )
                .classList.add(
                    "active"
                );

            document
                .getElementById(
                    "tab-btn-" + name
                )
                .classList.add(
                    "active"
                );

            setTimeout(
                () => {{

                    if (window.Plotly) {{

                        document
                            .querySelectorAll(
                                ".js-plotly-plot"
                            )
                            .forEach(
                                gd => {{

                                    try {{

                                        Plotly.Plots.resize(
                                            gd
                                        );

                                    }}
                                    catch(e) {{}}

                                }}
                            );

                    }}

                }},
                100
            );

        }}


        window.addEventListener(
            "load",
            function() {{

                if (window.Plotly) {{

                    document
                        .querySelectorAll(
                            ".js-plotly-plot"
                        )
                        .forEach(
                            gd => {{

                                try {{

                                    Plotly.Plots.resize(
                                        gd
                                    );

                                }}
                                catch(e) {{}}

                            }}
                        );

                }}

            }}
        );

    </script>

</body>

</html>
    """

    # ---------- Save HTML Next to Log ----------
    log_folder = os.path.dirname(
        os.path.abspath(
            log_file
        )
    )

    out_file = os.path.join(
        log_folder,
        "wrx_analysis.html"
    )

    with open(
        out_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(page_html)

    print("Saved interactive WRX analysis to:")

    print(out_file)


if __name__ == "__main__":
    main()

