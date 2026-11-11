# Contributing

Bug reports, reference charts and pull requests are welcome.

## Before your first pull request

The project is published under CC BY-NC-SA 4.0. The maintainer also needs the right to offer the work under other terms, such as a hosted paid tier or a commercial license. A contribution under the public license alone would block that.

So every contributor agrees to the grant below. State your agreement in the pull request with this line:

> I have read CONTRIBUTING.md and I agree to the contributor grant.

## Contributor grant

You keep the copyright in your contribution.

You grant Anthony David Adams, and anyone he authorizes, a perpetual, worldwide, non-exclusive, royalty-free, irrevocable license to use, copy, modify, publish, distribute and sublicense your contribution, in this project or elsewhere, under any license terms, commercial ones included.

You confirm that you wrote the contribution or have the right to submit it, and that it carries no terms that conflict with this grant.

## What a good change includes

- A test that fails before the change and passes after it.
- For anything that touches positions or chart logic, a reference: a published chart, a second engine, or a cited source.
- No code or data under the GPL or AGPL in `bodygraph/`. The optional Swiss Ephemeris add-on lives apart in `contrib/` for that reason.

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```
