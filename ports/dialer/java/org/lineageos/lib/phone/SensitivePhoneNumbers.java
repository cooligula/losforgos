package org.lineageos.lib.phone;

import android.content.Context;

import org.lineageos.lib.phone.spn.Item;

import java.util.ArrayList;

/**
 * Replacement for the LineageOS system library of the same name. It reads a list of sensitive
 * numbers that only the LineageOS system image ships, so outside of it the list is empty.
 */
public class SensitivePhoneNumbers {
  private static final SensitivePhoneNumbers INSTANCE = new SensitivePhoneNumbers();

  public static SensitivePhoneNumbers getInstance() {
    return INSTANCE;
  }

  public ArrayList<Item> getSensitivePnInfosForMcc(String mcc) {
    return new ArrayList<>();
  }

  public boolean isSensitiveNumber(Context context, String numberToCheck, int subId) {
    return false;
  }
}
