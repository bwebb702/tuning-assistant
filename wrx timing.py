import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
import seaborn as sns
import math
import itertools

file_path = "C:\\Users\\savet\\Desktop\\WRX\\"
log_path = "C:\\Users\\savet\\Desktop\\WRX\\Logs\\"
file_name = "wrx_rom_tables.xlsx"
log_file = "romraiderlog_20220702_175218.csv"

# renames the headers to be easy to read
headers = { "Time (msec)" : "Time", "CL/OL Fueling* (status)" : "CL/OL", "Engine Load* (g/rev)" : "g/rev",
           "Engine Speed (rpm)" : "RPM", "Feedback Knock Correction* (degrees)" : "FBKC",
           "Fine Learning Knock Correction* (degrees)" : "FLKC", "Fueling Final Base* (estimated AFR)" : "Est AFR",
           "Ignition Total Timing (degrees)" : "Timing", "Intake VVT Advance Angle Left (degrees)" : "AVCS",
           "Manifold Relative Pressure (psi)" : "MRP", "Mass Airflow (g/s)" : "g/s",
           "Throttle Opening Angle (%)" : "Throttle", "AEM UEGO Wideband [9600 baud] (AFR Gasoline)" : "WBO2",
            "Mass Airflow Sensor Voltage (V)" : "MAF Volts", "Intake Air Temperature (C)" : "IAT" }


def formatTable(df):
    # formats the ROM tables to make them usable from a copy/paste from ROMRaider
    load_headers = list(round(df.iloc[0,], 2))
    rpm_headers = list(df.iloc[1:, 0])
    df = df.iloc[1:, 1:]

    i = 0
    for col in df:
        df = df.rename(columns={col:load_headers[i]})
        i += 1

    i = 1
    for n in rpm_headers:
        df = df.rename(index={i:int(n)})
        i += 1

    return df

def getWOTruns(df):
    # filters out only WOT runs from the log
    df = df.loc[df['Throttle Opening Angle (%)'] > 97]

    if len(df) == 0:
        print("No WOT runs found!")

    # renames the headers in the log file for ease of use
    # helpful if log is written back to Excel file
    for key in headers:
        headers_to_change = list(df.iloc[0:])
        if key in headers_to_change:
            df = df.rename(columns={key: headers[key]})

    return df

def getIdle(df):
    # filters out only idle runs from the log
    df = df.loc[df['Engine Speed (rpm)'] < 1000]

    if len(df) == 0:
        print("No idle time found!")


    # renames the headers in the log file for ease of use
    # helpful if log is written back to Excel file
    for key in headers:
        headers_to_change = list(df.iloc[0:])
        if key in headers_to_change:
            df = df.rename(columns={key: headers[key]})

    return df

def getVE(df):
    # VE = (MAF / ((AMP * 1000) / (287.05 * (IAT + 273.15)) * 1000)) / (DISP * RPM / 3456 * 0.0283 / 60) * 100
    VE = []
    # IAT = 43
    ATM_KPA = 92
    DISP = 128.15
    logged_RPM = log['RPM'].tolist()
    logged_gs = log['g/rev'].tolist()
    logged_MRP = log['MRP'].tolist()
    logged_IAT = log['IAT'].tolist()

    for RPM, MAF, AMP, IAT in zip(logged_RPM, logged_gs, logged_MRP, logged_IAT):
    # for RPM, MAF, AMP in zip(logged_RPM, logged_gs, logged_MRP):
        AMP = (AMP * 6.89476) + ATM_KPA
        MAF = MAF * RPM / 60
        calc_VE = (MAF / ((AMP * 1000) / (287.05 * (IAT + 273.15)) * 1000)) / (DISP * RPM / 3456 * 0.0283 / 60)
        VE.append(round(calc_VE * 100, 3))

    df_VE = pd.DataFrame({'':VE}, index=logged_RPM)

    return df_VE

def getWOTparams(df, log):
    # gets the g/rev and rpm from log and creates array based on
    # the standard axis headers from the ROM table for comparison
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

def plotBoost(log, boost_table):
    # plots Boost vs RPM and AFR vs RPM
    boost_rpm = [800, 1200, 1600, 2470, 2600, 2800, 3600, 4000, 4400, 6000, 6800]
    peak_boost = 0

    try:
        boost = log['MRP'].tolist()
        AFR = log['WBO2'].tolist()
        est_AFR = log['Est AFR'].tolist()
        RPM = log['RPM'].tolist()
        tgt_boost = boost_table[100.00].tolist()

        for p_rpm, p_b in zip(RPM, boost):
            if p_b > peak_boost:
                peak_boost = p_b
                peak_rpm = p_rpm

        # smooths out missing RPM info
        # will remove once fixed
        # prev_rev = 0
        # for rev in RPM:
        #     if rev < prev_rev:
        #         AFR.pop(RPM.index(rev))
        #         est_AFR.pop(RPM.index(rev))
        #         boost.pop(RPM.index(rev))
        #         RPM.remove(rev)
        #     prev_rev = rev

        # plot boost and target boost vs RPM
        fig, ax = plt.subplots()
        ax.plot(RPM, boost, color='green')
        ax.plot(boost_rpm, tgt_boost, color='green', linestyle='dashed')
        ax.plot(peak_rpm, peak_boost, 'ro')
        plt.annotate(f'{peak_boost}psi', (peak_rpm, peak_boost), xytext=(0, 10), ha='center', textcoords='offset points')
        ax.set_ylim([0, 21])
        ax.set_xlim([2000, 6400])
        ax.set_ylabel("Boost", color='green')
        ax.set_xlabel("RPM")

        # plot AFR and Final Fueling base vs RPM
        ax2 = ax.twinx()
        ax2.plot(RPM, AFR, color='blue')
        ax2.plot(RPM, est_AFR, color='blue', linestyle='dashed')
        ax2.set_ylabel("AFR", color='blue')
        ax2.set_ylim((9, 17))
    except:
        print("No logged boost/AFR")
        return

def getKnocking(df, log):
    # gets any knock data from the run
    r, g = [], []
    logged_FBKC = log.loc[log['FBKC'] < 0]
    logged_FLKC = log.loc[log['FLKC'] < 0]
    logged_gs = logged_FLKC['g/rev'].tolist()
    logged_rpm = logged_FLKC['RPM'].tolist()

    if len(logged_FBKC.index) == 0 and len(logged_FLKC.index) == 0:
        print("No knocking found!")
        return g, r

    for fb in logged_FBKC:
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

    for fl in logged_FLKC:
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

def plotIdle(log):
    if len(log) == 0:
        return

    logged_afr = log['WBO2'].tolist()
    logged_rpm = log['RPM'].tolist()

    fig, ax = plt.subplots()
    ax.scatter(logged_rpm, logged_afr)
    # ax.set_xlabel("RPM")
    # ax.set_ylabel("AFR")
    # ax.set_xlim([500, 1000])
    # ax.set_ylim([14.0, 15.0])

# creates the maps
base_timing = formatTable(pd.read_excel(file_path + "wrx_rom_tables.xlsx", "base timing"))
knock_advance = formatTable(pd.read_excel(file_path + file_name, "kca"))
ol_fueling = formatTable(pd.read_excel(file_path + file_name, "ol fueling"))
boost = formatTable(pd.read_excel(file_path + file_name, "boost"))
avcs = formatTable(pd.read_excel(file_path + file_name, "avcs"))
# maf_scale = formatTable(pd.read_excel(file_path + file_name, "maf scale"))

# the run file
log = getWOTruns(pd.read_csv(log_path + log_file))
# log_idle = getIdle(pd.read_csv(log_path + log_file))

total_timing = knock_advance + base_timing

g, r = getWOTparams(total_timing, log)
knock_g, knock_r = getKnocking(total_timing, log)
g_avcs, r_avcs = getAVCS(avcs, log)
VE = getVE(log)
plotBoost(log, boost)
# plotIdle(log_idle)

fig, (ax_timing, ax_fuel) = plt.subplots(1, 2, figsize=(14,14))
fig.tight_layout()
ax_timing.set_aspect(0.75)
ax_fuel.set_aspect(0.75)
ax_timing.tick_params(rotation=0)
ax_fuel.tick_params(rotation=0)

fig2, (ax_avcs, ax_VE) = plt.subplots(1, 2, figsize=(14,14))
fig.tight_layout()
ax_avcs.set_aspect(0.75)
ax_VE.set_aspect(0.20)
ax_VE.tick_params(rotation=0)
ax_avcs.tick_params(rotation=0)

ax_timing.set_title("Total Timing")
ax_fuel.set_title("Open Loop Fueling")
ax_avcs.set_title("AVCS")
ax_VE.set_title("Volumetric Efficiency")

# plots heatmaps for timing, fuel, avcs
sns.heatmap(total_timing, ax=ax_timing, annot=True, fmt='.2f', cmap='Spectral_r', annot_kws={"fontsize":8}, cbar=False)
sns.heatmap(ol_fueling, ax=ax_fuel, annot=True, fmt='.2f', cmap='Spectral', annot_kws={"fontsize":8}, cbar=False)
sns.heatmap(avcs, ax=ax_avcs, annot=True, fmt='.2f', cmap='Spectral_r', annot_kws={"fontsize":8}, cbar=False)
sns.heatmap(VE, ax=ax_VE, annot=True, fmt='.2f', cmap='Spectral_r', annot_kws={"fontsize":8}, cbar=False)

# adds borders to the cells used in the run
for num, num2 in zip(g, r):
    ax_timing.add_patch(Rectangle((int(math.floor(num/2 * 10)), int(num2/400-2)), 1, 1, fill=False, edgecolor='black'))
    ax_fuel.add_patch(Rectangle((int(math.floor(num/2 * 10)), int(num2/400-2)), 1, 1, fill=False, edgecolor='black'))

# adds red border around cells with knocking recorded
for num, num2 in zip(knock_g, knock_r):
    ax_timing.add_patch(Rectangle((int(math.floor(num/2 * 10)), int(num2/400-2)), 1, 1, fill=False, edgecolor='red'))

# adds borders to the cells used in the run
for num, num2 in zip(g_avcs, r_avcs):
    ax_avcs.add_patch(Rectangle((int(math.floor(num/2 * 10) - .2), int(num2/400-1)), 1, 1, fill=False, edgecolor='black'))

plt.show()