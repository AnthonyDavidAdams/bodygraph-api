# Contributing

Bug reports, reference charts and pull requests are welcome.

## License of contributions

The project is MIT licensed. By opening a pull request you agree that your contribution is released under the same license.

## What a good change includes

- A test that fails before the change and passes after it.
- For anything that touches positions or chart logic, a reference: a published chart, a second engine, or a cited source.
- No code or data under the GPL or AGPL in `bodygraph/`. The optional Swiss Ephemeris add-on lives apart in `contrib/` for that reason.

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```
