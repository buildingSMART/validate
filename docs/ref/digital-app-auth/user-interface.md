## User Interface

The status of Digital Application Authentication checking will be displayed on the dashboard next to the icon
for the header check.

Models that do not include Digital Application Authentication will not display an additional icon:

```{image} ../_static/digital_app_auth_na.png
:alt: User interface for passing check of digital application authentication
:scale: 100 %
:align: center
```

Models from software tools that have correctly implemented Digital Application Authentication
and have not been modified downstream since export
will display an additional icon indicating a valid check:

```{image} ../_static/digital_app_auth_valid.png
:alt: User interface for passing check of digital application authentication
:scale: 100 %
:align: center
```

Models from software tools that have incorrectly implemented Digital Application Authentication and/or
have been modified downstream since export
will display an additional icon indicating a failed check:

```{image} ../_static/digital_app_auth_invalid.png
:alt: User interface for passing check of digital application authentication
:scale: 100 %
:align: center
:border: 4px
```

```{include} ./digital-app-auth/index.md
:heading-offset: 1
:relative-images:
```
