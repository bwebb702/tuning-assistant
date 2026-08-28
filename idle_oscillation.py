import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from tkinter import Tk, filedialog


LOG_FOLDER = r"C:\WRX\Logs"
OUTPUT_FILE = os.path.join(LOG_FOLDER, "AF_Correction_vs_Coolant_Temperature.html")


def select_log_files():
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    files = filedialog.askopenfilenames(
        title="Select CSV Log Files",
        initialdir=LOG_FOLDER,
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    root.destroy()
    return files


def find_alternating_extrema(df):
    """
    Reduce AF Correction data to alternating local minimum and maximum points.

    The resulting sequence will look like:
        minimum -> maximum -> minimum -> maximum -> ...

    Each AF Correction value retains its corresponding coolant temperature.
    """

    if len(df) < 3:
        return df.copy()

    values = df["AF Correction"].to_numpy(dtype=float)
    temps = df["Coolant Temperature"].to_numpy(dtype=float)

    extrema = []

    # Determine the direction between each consecutive point
    differences = np.diff(values)

    # Remove zero movements so flat sections do not create false extrema
    directions = np.sign(differences)

    for i in range(1, len(directions)):
        if directions[i] == 0:
            directions[i] = directions[i - 1]

    # Find local extrema
    for i in range(1, len(values) - 1):
        previous_direction = directions[i - 1]
        next_direction = directions[i]

        # Falling -> rising = local minimum
        if previous_direction < 0 and next_direction > 0:
            extrema.append({
                "index": i,
                "AF Correction": values[i],
                "Coolant Temperature": temps[i],
                "type": "min"
            })

        # Rising -> falling = local maximum
        elif previous_direction > 0 and next_direction < 0:
            extrema.append({
                "index": i,
                "AF Correction": values[i],
                "Coolant Temperature": temps[i],
                "type": "max"
            })

    if not extrema:
        return pd.DataFrame(columns=["Coolant Temperature", "AF Correction"])

    # Make sure the sequence starts with a minimum.
    # If the first detected point is a maximum, discard it.
    if extrema[0]["type"] == "max":
        extrema.pop(0)

    # Force the sequence to alternate min -> max -> min -> max.
    alternating = []

    for point in extrema:
        if not alternating or point["type"] != alternating[-1]["type"]:
            alternating.append(point)

    result = pd.DataFrame(alternating)

    return result[["Coolant Temperature", "AF Correction"]]


def load_log(filename):
    print(f"\nLoading: {os.path.basename(filename)}")

    try:
        df = pd.read_csv(filename, on_bad_lines="skip")
    except Exception as e:
        print(f"  Discarded - could not read file: {e}")
        return None

    required_columns = [
        "A/F Correction #1 (%)",
        "Coolant Temperature (F)",
        "CL/OL Fueling* (status)"
    ]

    # Discard file if any required column is missing
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        print(f"  Discarded - missing required fields: {missing_columns}")
        return None

    # Convert columns to numeric
    df["A/F Correction #1 (%)"] = pd.to_numeric(
        df["A/F Correction #1 (%)"],
        errors="coerce"
    )

    df["Coolant Temperature (F)"] = pd.to_numeric(
        df["Coolant Temperature (F)"],
        errors="coerce"
    )

    df["CL/OL Fueling* (status)"] = pd.to_numeric(
        df["CL/OL Fueling* (status)"],
        errors="coerce"
    )

    # ---------------------------------------------------------
    # Determine whether this is a startup log.
    #
    # Status 7 indicates startup/open-loop operation.
    # If the file never contains status 7, discard the
    # entire file.
    # ---------------------------------------------------------

    if not (df["CL/OL Fueling* (status)"] == 7).any():
        print("  Discarded - no CL/OL Fueling status 7 found")
        return None

    print("  Startup log confirmed - status 7 found")

    # ---------------------------------------------------------
    # For the actual AF correction analysis, only use
    # closed-loop status 8.
    # ---------------------------------------------------------

    df = df[df["CL/OL Fueling* (status)"] == 8].copy()

    # Remove rows where AF correction or coolant temperature
    # cannot be converted to numbers
    df = df.dropna(
        subset=[
            "A/F Correction #1 (%)",
            "Coolant Temperature (F)"
        ]
    )

    if df.empty:
        print("  Discarded - no valid status 8 data")
        return None

    # Rename columns for easier processing
    df = df.rename(
        columns={
            "A/F Correction #1 (%)": "AF Correction",
            "Coolant Temperature (F)": "Coolant Temperature"
        }
    )

    # Find alternating minimum -> maximum -> minimum points
    extrema_df = find_alternating_extrema(df)

    if extrema_df.empty:
        print("  Discarded - no AF correction extrema found")
        return None

    print(f"  Status 8 points: {len(df)}")
    print(f"  Extrema points:  {len(extrema_df)}")

    return extrema_df

def create_plot(files):
    fig = go.Figure()

    files_loaded = 0

    for filename in files:
        df = load_log(filename)

        if df is None or df.empty:
            continue

        files_loaded += 1

        # Use the CSV filename as the trace name
        trace_name = os.path.splitext(os.path.basename(filename))[0]

        fig.add_trace(
            go.Scatter(
                x=df["Coolant Temperature"],
                y=df["AF Correction"],
                mode="lines+markers",
                name=trace_name,
                hovertemplate=(
                    "Coolant Temp: %{x:.1f} °F"
                    "<br>AF Correction: %{y:.2f}%"
                    "<extra>%{fullData.name}</extra>"
                )
            )
        )

    if files_loaded == 0:
        print("\nNo valid log files were found.")
        return

    fig.update_layout(
        title="A/F Correction vs Coolant Temperature",
        xaxis_title="Coolant Temperature (°F)",
        yaxis_title="A/F Correction #1 (%)",
        template="plotly_white",
        hovermode="closest",
        width=1400,
        height=800,
        margin=dict(
            l=80,
            r=300,
            t=80,
            b=80
        ),
        legend=dict(
            title=dict(
                text="CSV Log File"
            ),
            orientation="v",
            x=1.02,
            y=1.0,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="black",
            borderwidth=1,
            font=dict(
                size=12
            )
        ),
        xaxis=dict(
            showgrid=True,
            zeroline=True
        ),
        yaxis=dict(
            showgrid=True,
            zeroline=True
        )
    )

    fig.write_html(
        OUTPUT_FILE,
        include_plotlyjs=True,
        full_html=True
    )

    print("\nPlot saved to:")
    print(OUTPUT_FILE)


def main():
    files = select_log_files()

    if not files:
        print("No files selected.")
        return

    print(f"\nSelected {len(files)} log file(s).")
    create_plot(files)


if __name__ == "__main__":
    main()