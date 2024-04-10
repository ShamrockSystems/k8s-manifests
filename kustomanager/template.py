from jinja2 import Environment, PackageLoader, select_autoescape

j2_env = Environment(
    loader=PackageLoader(package_name="kustomanager", package_path="templates"),
    autoescape=select_autoescape(),
    keep_trailing_newline=True,
)
