# Third-party material and provenance

## Captured provider documentation

Files under `data/evidence/` and the pinned copies under `examples/discovery-report/compatibility/data/evidence/` contain documentation captured from Amazon Web Services and OpenAI. These are third-party source material, not documentation authored by this project's contributors. The repository's MIT-0 and CC-BY-SA grants do not relicense these files.

`data/sources.json` and the embedded `sources` arrays in each `capabilities.json` record the publisher, original and retrieved URL, capture date, local path and SHA-256 for each snapshot. The example preserves its own evidence so historical replay does not silently inherit later catalog changes. Captures may be incomplete or outdated; consult the original source for current terms and behavior. Maintainers must confirm applicable redistribution terms before publishing these source captures in a release.

Provider websites: [AWS documentation](https://docs.aws.amazon.com/) and [OpenAI developer documentation](https://developers.openai.com/). No endorsement or additional rights are claimed. Keep any copyright and attribution notices present in the captures.

## Official cloud artwork

The artwork inventory, source revisions, hashes, permitted uses and transformations are recorded in [assets/cloud-icons/NOTICE.md](assets/cloud-icons/NOTICE.md) and its manifest. The pinned AWS artwork license is included as [AWS-LICENSE.txt](assets/cloud-icons/AWS-LICENSE.txt). Microsoft Azure artwork follows the limited architecture-documentation permission identified in the notice. These images are not relicensed as project code or text.

## Other dependencies

The runtime validators and packager use Python's standard library. Optional maintainer tooling and customer application dependencies are not redistributed as installed packages in this plugin. Installing or using those dependencies is subject to their own licenses.
