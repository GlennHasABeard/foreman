# Release checklist

Public acceptance contract. The published v1.2.1 tag, zip, and checksum stay as released. This file does not change bot defaults, routines, or setup behavior.

The zip, pin, privacy, visual, cost, and guard gates below stay in force. A share that uses a short description does not relax any of them.

## Gates that stay

- **Zip.** The release zip unpacks like published v1.1.2. After unzip into DEST, `DEST/foreman/README.md` exists and `DEST/foreman/foreman/standalone.json` exists. `README.md` is not at the zip root. The pack tool refuses any other layout.
- **Pin.** Install text names the published tag. `sha256sum -c SHA256SUMS` must pass before unzip. For v1.2.1 the tested zip is SHA256 `496973edd90168e48cba4798233dad7af0b3bb9513239e1188352ff290b352d7`. A mismatch stops the install.
- **Privacy.** The pack and the share text contain no private owner data. A profile or staging receipt is not a privacy pass.
- **Visual.** A release needs the seen light and dark matrix at the required phone and desktop widths. A string check is not that matrix.
- **Cost.** The cost check, spend caps, and the rule that a checksum or cap failure stops the run stay as they are. No share text may hide a cost or tell the bot to spend before the owner agrees.
- **Guards.** Setup does not start until the owner types "start setup". If `foreman/.template-master` exists, setup stops. These two guards must be in the complete setup the stranger receives, whether that setup is in the description or in an onboarding skill.

## Share acceptance

A share must deliver the complete setup to a stranger. Two carriers are allowed. A short description with neither carrier is an empty import and fails.

1. **Full description.** The share description itself is the complete setup.
2. **Onboarding skill.** The share description is short and accurate, and the included onboarding skill is the complete setup.

The proof is a stranger install of that share. A profile page, a staged card, or a receipt that the card was created is not proof.

For every bot, compare two texts word for word with the approved public source:

- the approved public description
- the full-setup carrier the stranger actually received (the description, or the included onboarding skill)

If either text is missing, shortened, or not the approved wording, that bot fails. All eight bots need their own stranger proof before the share set is accepted.

The stranger check reads the installed skill or description, confirms the complete setup is there, and confirms the bot is waiting for "start setup". It does not type "start setup" and it does not run setup. The test install is then deleted.

## Order for the v1.2.1 short cards

This order is the acceptance plan. It is not a license to publish cards from this checklist.

**Analytics Log is the pilot.** Its card is a short accurate description plus a complete v1.2.1 onboarding skill. The skill includes the "start setup" gate, the template-master stop, and the pin of zip SHA256 `496973edd90168e48cba4798233dad7af0b3bb9513239e1188352ff290b352d7`. The owner confirms that card. Then the stranger install above verifies the actual skill. If that install fails, stop. Do not make the other five short cards.

If the Analytics Log stranger install passes, make the same kind of card for Follow Audit and Shoutout Picker. Then make Reply Queue, Fan Finder, and Rerun Picker. Those three get new generic onboarding taken from their full public profiles. Do not copy Radar text. Do not copy private owner data.

Foreman and Follow Finder already carry the full setup in the description. Leave those two cards unchanged. They still need their own stranger proof with the other six.

No bot is accepted on a staging receipt alone.
