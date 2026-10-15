package com.android.common.io;

import android.database.Cursor;

/** Minimal replacement for the AOSP android-common helper of the same name. */
public final class MoreCloseables {
  private MoreCloseables() {}

  public static void closeQuietly(Cursor cursor) {
    if (cursor != null) {
      try {
        cursor.close();
      } catch (RuntimeException ignored) {
        // Nothing sensible to do.
      }
    }
  }
}
