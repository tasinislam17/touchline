"""Build a self-contained local review page from the latest V3 forecast."""
import json
import pathlib
ROOT=pathlib.Path(__file__).resolve().parent

def main():
    data=json.loads((ROOT/'reports/v3/review.json').read_text())
    template=(ROOT/'review/template.html').read_text()
    encoded=json.dumps(data,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    page=template.replace('/*__FORECAST_DATA__*/','window.FPL_DATA='+encoded+';')
    (ROOT/'review/index.html').write_text(page)
    print(ROOT/'review/index.html')

if __name__=='__main__':main()
