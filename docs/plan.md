# LineageOS apps for stock Android: build and release plan

Status: research only. Nothing has been created, pushed or signed. **Revision 2 (after John's answers)**: decisions are recorded in section 11, and sections 12 to 14 are new (package ids, memory tagging, Gcam Services Provider). Where those sections conflict with earlier text, they win. Findings come from reading the public upstream repos (shallow clones of the `lineage-24.0` branches, today's default) and a few docs pages. I could not list the whole LineageOS org (GitHub blocks that for me), so the app list below comes from probing known repo names. Please sanity-check it.

## 1. Recommendation in one paragraph (revision 1; see section 11 for what John decided)

Create **one new repo** (a "builder" repo), not forks. It holds a small manifest of upstream repos, a pinned upstream commit per app, a patch series per modified app, and GitHub Actions that clone upstream, apply patches, build, sign with one stable key, and publish one GitHub release per app version. Obtainium tracks each app with a release-title filter plus an APK-name filter. Roll out in three phases: the ~10 apps that already build with Gradle, then Messaging and Contacts, then the Dialer, which is the only genuinely hard port.

One surprise: **upstream Glimpse already implements Secure Review** (details in section 4), so that "modification" may shrink to testing it. That leaves the camera side as the open question.

## 2. Fork vs. single repo that applies patches

| | Forks of each upstream repo | Single builder repo + patches (recommended) |
|---|---|---|
| Repos to maintain | ~15 | 1 |
| Upstream sync | Merge or rebase in every fork, and fork Actions are off by default | One scheduled workflow bumps pinned SHAs and opens a PR |
| Modified vs. unmodified | Needs branches per fork, or two forks | The patch set is just an optional step in the same build |
| Obtainium | One source URL per fork | One source URL, filtered per app |
| Signing secrets | Duplicated per fork | Stored once |
| Risk | Drift, forgotten forks | A patch can stop applying after an upstream change; CI fails loudly and the PR does not merge |

Why this fits: the changes are small except the Dialer. Four of the ten modifications are one-line renames. Patches stay readable, and the diff against upstream is the patch itself.

Proposed layout:

```
apps.yml                # per app: upstream repo, branch, pinned SHA, applicationId, flags, variants
patches/<app>/*.patch   # only for modified variants
overlay/dialer/         # Gradle build files for the Dialer port (section 5)
scripts/                # fetch, patch, version, build, sign, release, gen-obtainium
.github/workflows/      # build (matrix), bump-upstream (scheduled), release
```

## 3. Which apps can actually be built standalone

Classified from each repo's build files and manifests (`lineage-24.0`).

**Tier 1: Gradle projects, install as ordinary apps**

| App | Upstream package | Notes |
|---|---|---|
| Glimpse (gallery) | `org.lineageos.glimpse` | minSdk 30. Release build is minified. |
| Aperture (camera) | `org.lineageos.aperture` | minSdk 26. Already has secure camera entry points. |
| Jelly (browser) | `org.lineageos.jelly` | minSdk 26 |
| Recorder | `org.lineageos.recorder` | minSdk 31 |
| Twelve (music) | `org.lineageos.twelve` | minSdk 30 |
| Camelot (PDF viewer) | `org.lineageos.camelot` | minSdk 35 |
| Etar (calendar) | `ws.xsoh.etar` | minSdk 23. Etar is also on F-Droid, so check you want the Lineage branch. |

**Tier 1b: Gradle, but the package id collides with AOSP apps, so they need a rename patch**

| App | Upstream package | Notes |
|---|---|---|
| ExactCalculator | `com.android.calculator2` | minSdk 31 |
| DeskClock | `com.android.deskclock` | compileSdk 37 |
| LatinIME (keyboard) | `com.android.inputmethod.latin` | Has native code, so the NDK is needed. Check on the first build. |

Whether these ids actually collide depends on the ROM. They do on AOSP-derived ROMs that ship them, so renaming is the safe default.

**Tier 2: Android.bp only, a Gradle port is required**

| App | SDK level in `Android.bp` | Notes |
|---|---|---|
| Messaging | `sdk_version: "current"` (public SDK only) | Easiest of the three. Authorities `com.android.messaging.*` need renaming. |
| Contacts | `system_current` | Privileged and shared-signature in the ROM. |
| Dialer | `system_current` | See section 5. |

**Tier 3: dropped by decision (John: user-space apps only, no system apps)**

- Updater: platform-signed, privileged, and does OTA updates, which is useless on GrapheneOS.
- Seedvault: needs privileged backup-transport access. GrapheneOS ships its own.
- AudioFX, FlipFlap, Profiles, Stk: platform signature, `android.uid.system` or `android.uid.phone`.
- Trebuchet, Launcher3, Settings, SetupWizard: platform components.
- Gallery2, Backgrounds: legacy / resource-only.
- Eleven, Calendar (17.x), Snap, Email, Terminal: old branches, not on the current release line.

Other upstream facts that affect the plan:

- **Every Gradle app has `versionCode = 1`** (Etar is 57), and release builds have **no signing config**. Upstream CI only runs `assembleDebug`. We must set versionCode ourselves or updates will never install.
- Gradle 9.4 / AGP 9.1 / JDK 17. The hosted `ubuntu-latest` image has the Android SDK, but compileSdk 36/37 platforms may need an `sdkmanager` install step.
- Upstream CI also checks that `Android.bp` stays in sync via `generateBp`. We skip that step.

## 4. The two modifications

### Glimpse "Secure Review": already upstream

I read `ViewActivity.kt`, `IntentsViewModel.kt` and `LocalPlayerViewModel.kt` in the current branch:

- The manifest registers `android.provider.action.REVIEW_SECURE` on `ViewActivity`.
- `ViewActivity` calls `setShowWhenLocked(true)` when the keyguard is locked and the action is `ACTION_REVIEW_SECURE`.
- The media list for a secure review is built **only from the URIs in the intent's data and clip data**, not from a MediaStore query. So the lockscreen view shows only what the camera handed over.
- Secure mode hides "use as", disables metadata editing, and routes share, adjust and delete through a keyguard-dismiss prompt.
- Aperture's own `openGallery()` sends `ACTION_REVIEW_SECURE` with the session's URIs while the device is locked. It tracks them in a list that clears on unlock.

So Aperture plus Glimpse already do this end to end. John uses the **Pixel Camera (GCam) with Gcam Services Provider** instead of Aperture, so the open question is that bridge, which section 14 covers. In short: the bridge does not support secure review today, and the fix probably belongs in the bridge rather than in Glimpse.

I have not run any of this on a device. It is a source reading only.

### Dialer rename and standalone install

Renaming the package alone is not enough. The manifest has several globally named things that would clash with the AOSP dialer:

- Package `com.android.dialer`, `coreApp="true"`
- Provider authorities: `com.android.dialer.annotatedcalllog`, `.blocking.filterednumberprovider`, `.files`, `.lookup`, `.phonelookuphistory`, `.preferredsimfallback`
- Custom permissions: `com.android.dialer.permission.DIALER_ORIGIN` and the `com.android.voicemail.permission.*` set
- Some of these strings are also hard-coded in Java (`Constants.java`, `LookupProvider.java`, `StatusSmsFetcher.java`)

With Gradle, `applicationId` can differ from `namespace`, so `R` and `BuildConfig` stay unchanged and the code does not need a package-wide rename. Authorities and permissions need a small patch (about 10 string sites plus the manifest).

**What stops working outside the system image.** The Dialer manifest requests many signature or privileged permissions (`MODIFY_PHONE_STATE`, `CAPTURE_AUDIO_OUTPUT`, `CONTROL_INCALL_EXPERIENCE`, `READ_PRIVILEGED_PHONE_STATE`, and others). A normal installed app does not get them. The dialer role itself (`DIAL`, `tel:` view, `InCallService`) works for any app, so calling should work. Expect these to be lost or degraded: call recording, parts of visual voicemail, and some in-call features. Which ones is something we find out only by running it.

## 5. Getting the Dialer to build (the hard part)

| Option | Verdict |
|---|---|
| A. Run Soong in CI with a trimmed Lineage tree | No. Tens of GB and a heavy sync. Not realistic on hosted runners. |
| B. Gradle project that wraps the unmodified upstream sources | **Recommended.** |

What I measured for option B:

- 926 Java files, 77 resource directories, 3 AIDL files, 20 `.proto` files.
- The `--extra-packages` list in `Android.bp` is not a blocker: every one of the 228 `R` imports is `com.android.dialer.R`, so one namespace works.
- Annotation processing: Dagger, AutoValue, Glide, plus the custom `dialer-rootcomponentprocessor` that lives in the same tree (needs its own small Gradle module).
- Protobuf-lite codegen and AIDL are supported by AGP and the protobuf Gradle plugin.
- Prebuilt jars are in `prebuilts/`. Other libraries (libphonenumber, guava, volley, commons-compress) come from Maven.
- `org.lineageos.lib.phone` is a separate Lineage-tree library. I have not located its repo yet, which is the first thing the spike must find.
- Hidden APIs: not heavy. I found reflection in 5 files (system property access, a telephony compat shim, Motorola and number-utils helpers). I could not compile it here because the Android SDK is unreachable from my sandbox, so **the real count of system-API calls is unknown** until the first compile. `system_current` means some calls may need the system stubs jar, and those would fail at runtime in a normal app.

Effort: a multi-day spike. Messaging should follow the same recipe with far less work, and Contacts sits in between.

Proposed order: spike Messaging first (public SDK, quickest proof of the Gradle-port approach), then Dialer, then Contacts.

If the Dialer proves too costly, the fallback is to ship everything else first. The Dialer would then be a separate phase with no impact on the other apps.

## 6. Signing

- **One long-lived key, generated once on your machine, never by the workflow.** A key created inside CI changes every run, and Android refuses to update an app whose signature changed (users would have to uninstall and lose data). I will write the generation script; you run it.
- Keystore: PKCS12, RSA 4096, validity 10,000+ days. Signing tool: `apksigner` with v2/v3 schemes (not debug keys, not v1-only).
- GitHub secrets (in a protected `release` environment limited to the main branch and tags): `KEYSTORE_B64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`. Keep an offline backup (password manager). If the key is lost, every installed app needs uninstalling.
- Build unsigned in Gradle, then `zipalign` + `apksigner sign` in a separate script step. The key never enters Gradle.
- One key for all apps is the simplest option. Per-app keys limit damage if one leaks, but we gain little for a personal project. This is one of your choices below.
- Workflows triggered by PRs or forks never get secrets.

What "properly signed" can and cannot buy you. Android itself does not label a correctly signed APK malicious. These are the real causes of install problems and warnings:

1. Debug-signed or unsigned APKs. Fixed by signing with the real key.
2. Package-id collisions with a system app (`INSTALL_FAILED_...` or "App not installed"). Fixed by the rename.
3. Old targetSdk. We keep the current one.
4. Play Protect heuristics, which only exist on devices with Google Play services (not on plain GrapheneOS). A new publisher asking for SMS and call-log permissions can still get a scan prompt on such devices. A stable key, a unique package id and a consistent update history reduce this, but I cannot promise it never appears.

## 7. Versioning, releases and Obtainium

**Version scheme** (Android needs the code to only go up):

- `versionCode = YYYYMMDDNN` (for example `2026101301`). It fits in 32 bits until the year 2147. `NN` counts builds that day, so a rebuild of the same upstream commit still updates.
- `versionName = <upstream versionName>.<YYYYMMDD>.<NN>` plus the upstream short SHA in the release notes.
- Applied by a scripted edit of each app's `versionCode`/`versionName` lines, since AGP 9 gives an init script little control over them.

**One GitHub release per app version** in the builder repo:

- Tag: `glimpse-v1.0.20261013.1`
- Title: `Glimpse 1.0.20261013.1`
- Assets: `glimpse-<version>-unmodified.apk`, `glimpse-<version>-modified.apk` (only if it has a patch set), plus `.sha256` files and a build attestation.
- Releases are published only for apps whose upstream pin changed.

**Obtainium setup**, one entry per app and variant (these option names exist on the Obtainium GitHub source and appear in Meshtastic's setup docs):

- Source URL: the builder repo
- Filter release titles by regex: `^Glimpse ` (isolates one app)
- Filter APKs by regex: `-modified\.apk$` or `-unmodified\.apk$` (picks the variant)
- Fallback to older releases: **ON**. Otherwise title filters fail with "Could not find a suitable release."
- The repo will include a generated `obtainium-apps.json` and `obtainium://app/...` links in the README, so one tap adds each app.

Open points I have not verified, and the first CI spike should test:

- How many recent releases Obtainium scans. If 15 apps release often, an app's latest release could fall off the page it reads. If so, we switch to fewer, grouped releases.
- The exact version-extraction setting, so Obtainium reads `1.0.20261013.1` out of a tag that starts with the app name. If it misbehaves, "release date as version" is the fallback.

**Modified and unmodified coexistence**

- Glimpse (and other same-id variants): both variants keep the upstream package id and the same key, so you can switch by installing the other APK. They cannot be installed side by side. If you want both at once, the modified one needs a different id, but then two galleries compete for the same intents. I recommend same id.
- Dialer: only the renamed build is installable standalone, so there is no "unmodified" Dialer to ship.
- Repo must be public so Obtainium needs no token.

## 8. Keeping up with upstream

- A scheduled workflow (cron on the 1st and 15th of each month, which approximates every two weeks) compares each pinned SHA with the upstream branch head. If different, it opens a "bump" PR that builds with patches applied.
- Merging that PR triggers the build, signing and release without any further steps. No unreviewed upstream code ships automatically. Upstream pushes automated translation imports and similar churn, so this keeps you in the loop without much work.
- A patch that no longer applies fails the PR, which is the signal to rebase it.
- Branch: track `lineage-24.0` for now. Note that old and new lines differ in minSdk (Camelot 35, Updater 34), so some apps will not install on older Android versions.

## 9. Hardening: worth it, but later and small

Cheap and worth doing during the build setup:

- Pin third-party actions to commit SHAs; restrict `GITHUB_TOKEN` permissions per job.
- Build attestations (`actions/attest-build-provenance`) and `.sha256` files.
- Gradle dependency verification to pin Maven artifacts.
- Keep release builds minified (already the upstream default).

Not worth doing now: patching app behavior (stripping permissions, removing network access). GrapheneOS already gives per-app network and sensor toggles, and this adds patch maintenance. Reproducible builds are a nice-to-have, not a first-phase goal.

## 10. Phases

0. **Gcam bridge probe**: debug build of the bridge, device capture, then the bridge patch (section 14). It can run in parallel with phase 1 because Glimpse does not need to change first.
1. **Foundation**: new repo, `apps.yml`, build/sign/release scripts, key generation. Ship Glimpse and Aperture end to end as the proof, including the Obtainium checks.
2. **Rest of Tier 1 and 1b**: Jelly, Recorder, Twelve, Camelot, Etar, then the renamed ExactCalculator, DeskClock and LatinIME.
3. **Messaging**, as the Gradle-port proof.
4. **Dialer**, then Contacts.
5. Hardening items from section 9.

## 11. Decisions (John, 2026-10-15)

1. One builder repo with patches. Decided.
2. Camera: Pixel Camera with Gcam Services Provider (Photos flavor), with Glimpse as the gallery. Secure review must work through it. See section 14.
3. Package prefix `org.losforgos.*` for all apps. Apps must work with hardware memory tagging on GrapheneOS. See sections 12 and 13.
4. Only user-space apps. Updater, Seedvault and all system or platform apps are dropped. Messaging, Contacts and the Dialer stay because they can run as ordinary apps.
5. Upstream bumps: a PR every two weeks. Once it is accepted and patches apply without conflicts, CI builds and releases automatically. I read "accepted" as "you merge it"; the alternative is auto-merge when green, which I advise against because it ships unreviewed upstream code.
6. One signing key for all apps.
7. Repo "LineageOS Apps for GrapheneOS", short name `losforgos`, public. John creates it and gives me SSH access.

### Still open

- SSH access to the repo, and a place for the signing secrets (John adds them himself; I never see the key).
- A device capture of the intent Pixel Camera sends on the lockscreen (section 14).
- Whether to ship a patched Gcam Services Provider ourselves, and whether to offer the fix upstream.
- Confirm the app list in section 3 has nothing missing.

## 12. Package ids

Every app gets an `org.losforgos.<name>` application id, set through Gradle's `applicationId` only. The Kotlin/Java `namespace` stays as upstream, so no source files are renamed. I checked the Gradle apps for hard-coded package strings and found few:

- Class names in navigation XML and fragments (follow the namespace, unaffected).
- Private intent action strings in Twelve and DeskClock (internal, unaffected).
- `shortcuts.xml` in Recorder has a hard-coded `targetPackage` (needs a one-line patch to use the new id).
- Preinstall and stopped-state XML files in each repo are system image files and are not packaged in the APK.

Proposed ids: `org.losforgos.glimpse`, `.aperture`, `.jelly`, `.recorder`, `.twelve`, `.camelot`, `.etar`, `.calculator`, `.deskclock`, `.keyboard`, `.messaging`, `.contacts`, `.dialer`.

Consequences:
- The "unmodified" and "modified" Glimpse variants share `org.losforgos.glimpse`. You can switch by installing the other APK, but not run both.
- Obtainium filters from section 7 stay as designed, with new names.
- Cross-app calls by package name (for example, Aperture opening a specific gallery) are by intent, so they keep working.

## 13. Memory tagging (MTE) and native code

I checked every app's sources for native code:

| App | Native code |
|---|---|
| LatinIME (keyboard) | Yes: a C++ dictionary engine through JNI. The highest risk. |
| Aperture | Yes: `zxing-cpp-android` for QR scanning. |
| Messaging | Yes: a `giftranscode` JNI library. |
| Glimpse, Jelly, Recorder, Twelve, Camelot, Etar, ExactCalculator, DeskClock, Contacts, Dialer | None in the repo. Third-party libraries could still ship `.so` files, so CI checks the built APK. |

What this means:
- Memory tagging only affects native code. Apps with no native libraries are unaffected, because the Java/Kotlin runtime is not tagged.
- CI step for every built APK: list the `.so` files, and fail if one is not 16 KB aligned (`zipalign -P 16`) or is stored compressed. This catches the usual compatibility problems before a device sees them.
- I cannot test MTE in CI. Hosted runners have no MTE hardware. The check is manual on your device (Pixel 8 or newer): run each native-bearing app with memory tagging in its strictest mode and watch for crashes.
- If an app is clean, we can opt it in with `android:memtagMode="sync"` in its manifest. That is a hardening gain, but only after your test. If an app crashes, the cause is usually a real memory bug in the native code. Then we either patch it, or document that the app needs GrapheneOS's per-app exploit-protection compatibility toggle.
- Some details about which GrapheneOS settings are on by default are from my memory. The GrapheneOS features page only confirmed the allocator, kernel and Vanadium parts, so verify the per-app setting names on your device.

## 14. Secure review through Gcam Services Provider (Photos)

What I read in the upstream source (`lukaspieper/Gcam-Services-Provider`, MIT):

- The *photos* flavor installs an app with package id `com.google.android.apps.photos`. Pixel Camera sees "Google Photos" present and hands its gallery button to it.
- It declares one activity, `PreviewRedirectActivity`, listening for `REVIEW`, `REVIEW_SECURE`, and Google's own `photos.mars.api.ACTION_REVIEW` and `..._REVIEW_SECURE` actions on `content:` image and video URIs.
- Its entire logic is: take `intent.data`, start a new `ACTION_VIEW` with only that URI, then finish.

So it **does not support secure review**. For a secure launch it:
1. Drops the action, so Glimpse sees a plain view and never enters secure mode (no lockscreen display, no read-only mode).
2. Drops the clip data, so only one URI survives, not the whole secure session.
3. Drops the URI read-grant flag.
4. Has no `showWhenLocked`, and Glimpse is started by a normal activity, so on a locked screen the result is likely a keyguard prompt or nothing. I have not tested this.

Proposed fix, in order of preference:
1. **Patched bridge in our repo**: forward `REVIEW_SECURE` (both the AOSP and the Google action name) with its action, data, clip data, flags and extras to Glimpse's secure-review entry point, and make the redirect activity `showWhenLocked`. Ship it as one more release. Since it keeps the Photos package id, it can only be installed over the upstream bridge if signed by the same key, so Obtainium users must uninstall the upstream one first.
2. **Send the same change upstream** to the bridge author, so the patch can later disappear.
3. Fall back to adding the Google "mars" action name to Glimpse itself, only if the capture below shows Pixel Camera sends data Glimpse cannot already read.

Unknowns that need a device capture before I write any code:
- What exactly Pixel Camera sends for the lockscreen gallery button: action name, data, clip data, flags, and any extras that list the session's photos. The bridge logs `intent.toString()`, which hides extras, so I would add a small debug build that dumps everything.
- Whether the URIs Pixel Camera passes are MediaStore URIs. Glimpse reloads secure items from MediaStore by URI, so non-MediaStore URIs would need handling.
- Whether Pixel Camera sends the whole session or only the last photo. If only one URI, "show only this session's photos" needs a different source of truth.

How I'd get the capture: you install the debug bridge build (I'll publish it from the repo), open Pixel Camera from the lockscreen, take a few photos, tap the thumbnail, and send me `adb logcat` output. About two minutes of work for you.

