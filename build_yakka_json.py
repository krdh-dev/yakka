#!/usr/bin/env python3
"""厚労省の薬価基準収載品目リスト(Excel)を、検索アプリ用の data.json に変換する。

使い方:
  python build_yakka_json.py <Excelを置いたフォルダ> [出力先 data.json]

フォルダ内の tp{YYYYMMDD}-01_01〜04.xlsx を読む。
同じ種別(01〜04)が複数あれば、日付が最新のものを使う。
列構成が想定と違う場合はエラーで止める(古いデータを黙って出さないため)。
"""
import glob, gzip, json, os, re, sys
from datetime import datetime, timezone
from openpyxl import load_workbook

# 1行目の見出し。None は見出しのない列(局/麻/※などの印が入る)
EXPECTED = ['区分', '薬価基準収載医薬品コード', '成分名', '規格', None, None, None,
            '品名', 'メーカー名', '診療報酬において加算等の算定対象となる後発医薬品',
            '先発医薬品', '同一剤形・規格の後発医薬品がある先発医薬品', '薬価',
            '経過措置による使用期限', '備考']

# JSONに出す列(短いキー)。印3列(局/麻/※)は1列にまとめる
COLS = ['kubun', 'code', 'ingredient', 'spec', 'marks', 'name', 'maker',
        'generic', 'brand', 'hasGeneric', 'price', 'expire', 'note']


def pick_files(folder):
    best = {}  # 種別(01〜04) -> (日付, パス)
    for p in glob.glob(os.path.join(folder, '*.xlsx')):
        m = re.fullmatch(r'tp(\d{8})-01_0([1-4])\.xlsx', os.path.basename(p))
        if m and (m.group(2) not in best or m.group(1) > best[m.group(2)][0]):
            best[m.group(2)] = (m.group(1), p)
    return best


def clean(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def read_sheet(path):
    ws = load_workbook(path, read_only=True, data_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True)
    header = [clean(h) for h in list(next(it))[:15]]
    if header != EXPECTED:
        raise SystemExit(f'列構成が想定と違います: {os.path.basename(path)}\n{header}')
    for r in it:
        r = [clean(c) for c in list(r)[:15]]
        if not r[1]:          # コードが空の行(空行・注記)は捨てる
            continue
        marks = ''.join(x for x in r[4:7] if x)
        yield [r[0], r[1], r[2], r[3], marks or None, r[7], r[8], r[9], r[10], r[11],
               r[12], r[13], r[14]]


def main():
    folder = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'data.json'
    files = pick_files(folder)
    missing = [k for k in '1234' if k not in files]
    if missing:
        raise SystemExit(f'ファイルが足りません(種別 0{", 0".join(missing)})')

    rows, sources = [], []
    for k in '1234':
        date, path = files[k]
        n0 = len(rows)
        rows.extend(read_sheet(path))
        sources.append({'file': os.path.basename(path), 'date': date, 'count': len(rows) - n0})

    # 適用日 = 内用薬・注射薬・外用薬(01〜03)のファイル日付の最大値。歯科(04)は更新が少ないので除外
    d = max(files[k][0] for k in '123')
    data = {'appliedDate': f'{d[:4]}-{d[4:6]}-{d[6:]}',
            'generatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'sources': sources, 'cols': COLS, 'rows': rows}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    size = os.path.getsize(out)
    gz = len(gzip.compress(open(out, 'rb').read()))
    print(f'適用日 {data["appliedDate"]} / {len(rows)}件 / {size/1e6:.2f}MB (gzip {gz/1e6:.2f}MB) -> {out}')
    for s in sources:
        print(' ', s)


if __name__ == '__main__':
    main()
