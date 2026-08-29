/**
 * GTFB — Anti-Distraction Suite
 * Schedule Window Evaluation Utilities
 */

/**
 * Determines whether the current time falls inside a scheduled window.
 * Handles same-day windows as well as overnight schedules crossing midnight (e.g. 22:00 -> 06:00).
 *
 * @param {Date|number|string} now - Current Date instance, timestamp, or date string
 * @param {number} startHour - Schedule start hour (0-23)
 * @param {number} startMinute - Schedule start minute (0-59)
 * @param {number} endHour - Schedule end hour (0-23)
 * @param {number} endMinute - Schedule end minute (0-59)
 * @returns {boolean} True if the time is inside the scheduled blocking window, false otherwise
 */
export function isTimeInWindow(now, startHour, startMinute, endHour, endMinute) {
  const date = now instanceof Date ? now : new Date(now);
  if (isNaN(date.getTime())) {
    return false;
  }

  const currentMinutes = date.getHours() * 60 + date.getMinutes();
  const startMinutes = startHour * 60 + startMinute;
  const endMinutes = endHour * 60 + endMinute;

  if (startMinutes === endMinutes) {
    return false; // Disabled or zero-length window
  }

  if (startMinutes < endMinutes) {
    // Standard same-day window (e.g. 09:00 -> 17:00)
    return currentMinutes >= startMinutes && currentMinutes < endMinutes;
  } else {
    // Overnight window crossing midnight (e.g. 22:00 -> 06:00)
    return currentMinutes >= startMinutes || currentMinutes < endMinutes;
  }
}
