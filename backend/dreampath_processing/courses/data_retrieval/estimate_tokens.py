import argparse
import pandas as pd
import tiktoken

def count_tokens(text: str, enc) -> int:
    if not isinstance(text, str) or not text.strip():
        return 0
    return len(enc.encode(text))

def analyze_csv(path, columns=None, model="text-embedding-3-small"):
    enc = tiktoken.encoding_for_model(model)
    df = pd.read_csv(path)

    if not columns:
        columns = df.columns.tolist()

    stats = []
    for col in columns:
        if col not in df.columns:
            continue
        lens = [count_tokens(val, enc) for val in df[col].astype(str).tolist()]
        avg_len = sum(lens)/len(lens) if lens else 0
        max_len = max(lens) if lens else 0
        stats.append((col, avg_len, max_len))
    return stats

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Path to CSV")
    ap.add_argument("--cols", nargs="+", help="Columns to analyze (default: all)")
    args = ap.parse_args()

    results = analyze_csv(args.csv, args.cols)
    print(f"Token stats for {args.csv}:")
    for col, avg_len, max_len in results:
        print(f"  {col:20s} avg={avg_len:.1f} max={max_len}")