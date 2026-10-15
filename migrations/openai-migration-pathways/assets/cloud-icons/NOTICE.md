# Official architecture artwork

This subset is for architecture diagrams and related documentation. It is not
covered by a general software license. `manifest.json` records each exact
asset's source, release, original and embedded SHA-256, attribution and
usage/license terms. The bundled diagram helper verifies the asset checksums
before embedding. These hashes are integrity records, not signatures; no custom
signed runtime is required.

## Microsoft Azure

Sixteen SVGs originate in Microsoft's `Azure_Public_Service_Icons_V24.zip`, the
July 2026 release. Archive SHA-256:
`921594ccd1bf3d9c0a1bd7b6d924e050551a59342f2b353bb74bdcf761c35141`.

Source: https://arch-center.azureedge.net/icons/Azure_Public_Service_Icons_V24.zip

Usage authority, observed 2026-09-01:
https://learn.microsoft.com/en-us/azure/architecture/icons/

Microsoft permits copying, distributing and displaying these icons for
architecture diagrams, training materials and documentation, and reserves all
other rights. Keep service names nearby. Do not crop, flip, rotate, distort,
recolor or change the artwork's shapes. This is a restricted permitted-use
grant, not a general open-source artwork license.

The original seven assets were serialized with locally scoped IDs. The nine
assets added for application, agent, data, search, observability and security
services retain the exact official SVG bytes and are isolated as embedded image
documents. The manifest records the applicable transformation and both source
and embedded digests. Rendering preserves artwork at 48px with its aspect ratio.

## Amazon Web Services

Twenty unchanged 64-by-64 service PNGs are published in AWS-owned
`awslabs/aws-icons-for-plantuml`, release `v23.0`, pinned commit
`50efda948226ff4e06937596201528b707ef3ef9`:
https://github.com/awslabs/aws-icons-for-plantuml/tree/50efda948226ff4e06937596201528b707ef3ef9

Attribution: Amazon Web Services (AWS), AWS Architecture Icons; published by
awslabs/aws-icons-for-plantuml. The icon package is CC-BY-ND-2.0:
https://creativecommons.org/licenses/by-nd/2.0/

`AWS-LICENSE.txt` retains the complete pinned license bytes, SHA-256
`79bb313f94c809be6a35b624b7e58c9480335bbb54c8d9b1546d1333481a9fac`.
The separate architecture-icons usage page is
https://aws.amazon.com/architecture/icons/.

The pinned repository's service-PNG generation branch copies the original
official-package PNGs. That is source-code evidence for official origin, not an
independent comparison with the omitted upstream archive. These are accurately
described as pinned AWS-owned published rasters, not raw SVGs or verified bytes
from the unavailable July 2026 AWS ZIP. No unofficial, category-cropped,
recolored, dark-mode or simplified artwork is included.

All PNG bytes are unchanged, including the original color and dimensions
metadata. Icons display at 48px. The diagram's
text, boundaries and connections remain editable vectors, but AWS artwork is
raster and can blur at substantial magnification.

## Package origin

The original fourteen files and manifest records came from the prior project's
pinned architecture subset. The additional twenty-two assets were selected from
the same pinned AWS commit and Microsoft V24 archive on 2026-09-04. Only icons
needed by the migration architecture are bundled; the complete upstream packs
are not shipped. The prior project's vendoring tools and custom runtime are not
dependencies of this plugin.
