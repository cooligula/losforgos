package com.android.dialer.phonematch;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.provider.ContactsContract.PhoneLookup;
import android.telephony.SubscriptionInfo;
import android.telephony.SubscriptionManager;
import android.telephony.TelephonyManager;
import android.text.TextUtils;
import android.util.Log;
import com.google.i18n.phonenumbers.PhoneNumberUtil;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Finds the contact of a number whichever way the country prefix is written.
 *
 * <p>Android's contact lookup compares "612345678" and "+34612345678" by guessing the country, and
 * often misses. A phone with two SIMs receives numbers without prefix from each SIM's own country,
 * so no single guess works. This class reads a number without prefix as a national number of every
 * country of the SIMs in the phone, and a number with a prefix as itself. It asks Android's lookup
 * for the other ways of writing the number, and only accepts a contact whose stored number is the
 * same number (see {@link NumberKeys}), so a different explicit prefix never matches.
 */
public final class NationalNumberMatcher {
  private static final String TAG = "NationalNumberMatcher";

  private NationalNumberMatcher() {}

  /**
   * Returns the number to look up in the contacts: {@code number} itself when Android already finds
   * a contact for it, the contact's stored number when only another way of writing the number
   * finds one, and {@code number} again when nothing does. May be called on any thread; it makes a
   * few quick queries.
   */
  public static String resolveForLookup(Context context, String number) {
    if (TextUtils.isEmpty(number) || number.indexOf('@') >= 0 || number.indexOf('*') >= 0
        || number.indexOf('#') >= 0) {
      return number;
    }
    if (context.checkSelfPermission(Manifest.permission.READ_CONTACTS)
        != PackageManager.PERMISSION_GRANTED) {
      return number;
    }
    try {
      Set<String> regions = regions(context);
      Set<String> keys = NumberKeys.of(number, regions);
      if (keys.isEmpty()) {
        return number; // short number, service code or not a phone number
      }
      if (findStoredNumber(context, number, null, regions) != null) {
        return number; // Android finds a contact on its own
      }
      for (String alternative : NumberKeys.alternatives(number, regions)) {
        String stored = findStoredNumber(context, alternative, keys, regions);
        if (stored != null) {
          Log.i(TAG, "matched a contact through another way of writing the number");
          return stored;
        }
      }
    } catch (RuntimeException e) {
      Log.w(TAG, "number matching failed, using the number as it is", e);
    }
    return number;
  }

  /**
   * Looks {@code lookup} up in the contacts and returns the stored number of the first contact
   * whose number has a key in common with {@code required}, or of any contact if {@code required}
   * is null.
   */
  private static String findStoredNumber(
      Context context, String lookup, Set<String> required, Set<String> regions) {
    Uri uri = Uri.withAppendedPath(PhoneLookup.CONTENT_FILTER_URI, Uri.encode(lookup));
    try (Cursor cursor =
        context.getContentResolver().query(uri, new String[] {PhoneLookup.NUMBER}, null, null, null)) {
      if (cursor == null) {
        return null;
      }
      while (cursor.moveToNext()) {
        String stored = cursor.getString(0);
        if (required == null) {
          return stored == null ? lookup : stored;
        }
        if (stored != null) {
          for (String key : NumberKeys.of(stored, regions)) {
            if (required.contains(key)) {
              return stored;
            }
          }
        }
      }
    }
    return null;
  }

  /** The countries of every SIM in the phone, the network they are on, and the phone's locale. */
  private static Set<String> regions(Context context) {
    Set<String> regions = new LinkedHashSet<>();
    try {
      TelephonyManager telephony = context.getSystemService(TelephonyManager.class);
      if (telephony != null) {
        add(regions, telephony.getSimCountryIso());
        add(regions, telephony.getNetworkCountryIso());
        SubscriptionManager subscriptions = context.getSystemService(SubscriptionManager.class);
        List<SubscriptionInfo> infos =
            subscriptions == null ? null : subscriptions.getActiveSubscriptionInfoList();
        if (infos != null) {
          for (SubscriptionInfo info : infos) {
            add(regions, info.getCountryIso());
            TelephonyManager forSim = telephony.createForSubscriptionId(info.getSubscriptionId());
            add(regions, forSim.getSimCountryIso());
            add(regions, forSim.getNetworkCountryIso());
          }
        }
      }
    } catch (RuntimeException e) {
      // No permission to list the SIMs: the countries known so far, and the locale, still apply.
    }
    add(regions, Locale.getDefault().getCountry());
    return regions;
  }

  private static void add(Set<String> regions, String iso) {
    if (TextUtils.isEmpty(iso)) {
      return;
    }
    String region = iso.toUpperCase(Locale.US);
    if (PhoneNumberUtil.getInstance().getSupportedRegions().contains(region)) {
      regions.add(region);
    }
  }
}
