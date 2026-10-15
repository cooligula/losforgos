package com.android.dialer.phonematch;

import com.google.i18n.phonenumbers.NumberParseException;
import com.google.i18n.phonenumbers.PhoneNumberUtil;
import com.google.i18n.phonenumbers.PhoneNumberUtil.PhoneNumberFormat;
import com.google.i18n.phonenumbers.Phonenumber.PhoneNumber;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * Keys that identify a phone number independently of how its country prefix is written.
 *
 * <p>Two numbers are the same person's number when their key sets share a key. A number with an
 * international prefix ("+34 612 34 56 78", "0034612345678") has one key, its E.164 form. A number
 * without one ("612345678", "0470 12 34 56") is read as a national number of each of the given
 * regions, so it has the E.164 form of every region in which it is valid, plus its bare digits.
 * Numbers with different explicit country prefixes therefore never match.
 */
final class NumberKeys {
  /** Shorter numbers (emergency and service codes) are never matched this way. */
  static final int MIN_DIGITS = 7;

  private NumberKeys() {}

  static Set<String> of(String number, Collection<String> regions) {
    Set<String> keys = new LinkedHashSet<>();
    Parsed parsed = Parsed.read(number);
    if (parsed == null) {
      return keys;
    }
    PhoneNumberUtil util = PhoneNumberUtil.getInstance();
    if (parsed.international != null) {
      keys.add(internationalKey(util, parsed.international));
      return keys;
    }
    for (String region : regions) {
      PhoneNumber national = parseNational(util, parsed.digits, region);
      if (national != null) {
        keys.add(util.format(national, PhoneNumberFormat.E164));
      }
    }
    keys.add("d:" + parsed.digits);
    return keys;
  }

  /**
   * Other ways of writing {@code number} that Android's own contact lookup can match against a
   * contact saved with or without a prefix. The caller still has to check the matches with {@link
   * #of}, because Android's lookup ignores country prefixes when it compares.
   */
  static List<String> alternatives(String number, Collection<String> regions) {
    List<String> alternatives = new ArrayList<>();
    Parsed parsed = Parsed.read(number);
    if (parsed == null) {
      return alternatives;
    }
    PhoneNumberUtil util = PhoneNumberUtil.getInstance();
    if (parsed.international != null) {
      try {
        PhoneNumber phone = util.parse("+" + parsed.international, null);
        if (util.isValidNumber(phone)) {
          alternatives.add(util.format(phone, PhoneNumberFormat.NATIONAL).replaceAll("[^0-9]", ""));
        }
      } catch (NumberParseException e) {
        // No alternatives for a number that cannot be read.
      }
      alternatives.add("00" + parsed.international);
    } else {
      for (String region : regions) {
        PhoneNumber national = parseNational(util, parsed.digits, region);
        if (national != null) {
          String e164 = util.format(national, PhoneNumberFormat.E164);
          alternatives.add(e164);
          alternatives.add("00" + e164.substring(1));
        }
      }
    }
    alternatives.removeAll(java.util.Collections.singleton(number));
    return new ArrayList<>(new LinkedHashSet<>(alternatives));
  }

  private static PhoneNumber parseNational(PhoneNumberUtil util, String digits, String region) {
    try {
      PhoneNumber parsed = util.parse(digits, region);
      return util.isValidNumber(parsed) ? parsed : null;
    } catch (NumberParseException e) {
      return null; // Not a number of this region.
    }
  }

  /** The digits of a number, and its digits with the country code if it has a prefix. */
  private static final class Parsed {
    final String digits;
    /** Digits starting with the country code, or null when the number has no prefix. */
    final String international;

    private Parsed(String digits, String international) {
      this.digits = digits;
      this.international = international;
    }

    /** Returns null for service codes, short numbers and empty input. */
    static Parsed read(String number) {
      if (number == null) {
        return null;
      }
      StringBuilder digits = new StringBuilder();
      boolean plus = false;
      for (int i = 0; i < number.length(); i++) {
        char c = number.charAt(i);
        if (c >= '0' && c <= '9') {
          digits.append(c);
        } else if (c == '+' && digits.length() == 0) {
          plus = true;
        } else if (c == '*' || c == '#') {
          return null;
        } else if (c == ',' || c == ';' || c == 'p' || c == 'P' || c == 'w' || c == 'W') {
          break; // post-dial digits are not part of the number
        }
      }
      if (digits.length() < MIN_DIGITS) {
        return null;
      }
      String all = digits.toString();
      String international = plus ? all : (all.startsWith("00") ? all.substring(2) : null);
      return new Parsed(all, international);
    }
  }

  private static String internationalKey(PhoneNumberUtil util, String digitsWithCountryCode) {
    String plusForm = "+" + digitsWithCountryCode;
    try {
      PhoneNumber parsed = util.parse(plusForm, null);
      if (util.isValidNumber(parsed)) {
        return util.format(parsed, PhoneNumberFormat.E164);
      }
    } catch (NumberParseException e) {
      // Fall through to the plain form.
    }
    return plusForm;
  }
}
