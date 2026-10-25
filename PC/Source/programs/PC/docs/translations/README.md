# Maintaining translated integration documents

English is the default. The `exchange/` directory contains directly authored
text for all 34 application languages, including separate Traditional Chinese
regional editions and both Mongolian scripts. Do not replace an edition with
an English redirect or use an external automatic translation service.

Each catalog contains 19 navigation/section labels and 14 substantive paragraphs.
Their stable positions are defined by `TEXT_HEADINGS` in
`packaging/generate_exchange_documents.py`. Apply factual corrections to every
catalog before rendering. Literal API names, JSON keys, executable commands and
test vectors are shared and must remain byte-identical across editions.

From the source root, run the generator with the documentation-only dependency
`Markdown==3.7`. This dependency is not needed by the node or wallet runtime.

```powershell
python packaging/generate_exchange_documents.py
```

The generator writes six current-update topics in Markdown and HTML into both
`docs/i18n/` and `programs/PC/docs/i18n/`, an English default index, metadata and a
file-hash manifest. The extended English references remain at their original
paths. The translated scope covers the current integration update, not all
historical whitepapers or release history. Repackage documentation alongside the
unchanged verified executable when only documentation changes.
