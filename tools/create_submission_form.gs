/**
 * Scout Event Finder - "Submit an event" form.
 * Run createEventSubmissionForm() once from script.google.com (New project, paste, Run).
 * It creates, in your own Google account:
 *   - a Google Form people use to send in events
 *   - a response Sheet with an "Approved (type yes)" column you fill in
 *   - an "Approved" tab showing only approved rows, WITHOUT the submitter's email
 * Then publish ONLY the "Approved" tab as CSV (File > Share > Publish to web) and send that link
 * to be saved in data/submissions.json. Nothing appears on the site until you type "yes".
 */
function createEventSubmissionForm() {
  const form = FormApp.create('Scout Event Finder - Submit an event');
  form.setDescription(
    'Know about a Scouting event or a kid-friendly public program around Los Angeles? Share it here. ' +
    'A leader reviews every submission before it appears on the Scout Event Finder.');
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);

  form.addTextItem().setTitle('Event name').setRequired(true);
  form.addTextItem().setTitle('Link to the event page or registration').setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextIsUrl().build());
  form.addDateItem().setTitle('Start date').setRequired(true);
  form.addTimeItem().setTitle('Start time');
  form.addDateItem().setTitle('End date');
  form.addTimeItem().setTitle('End time');
  form.addTextItem().setTitle('Location / address').setRequired(true);
  form.addTextItem().setTitle('ZIP code').setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextMatchesPattern('^\\d{5}$')
      .setHelpText('Five digits, e.g. 91401').build());
  form.addCheckboxItem().setTitle('Who is it for?').setRequired(true)
    .setChoiceValues(['Cub Scouts', 'Scouts BSA', 'Venturing', 'Sea Scouts', 'Adults / Leaders', 'Families']);
  form.addMultipleChoiceItem().setTitle('Is this a Scout event or a public program?').setRequired(true)
    .setChoiceValues(['Scout event (council, district, unit, OA or merit badge program)',
                      'Public program (not run by Scouting)']);
  form.addTextItem().setTitle('Organizer');
  form.addTextItem().setTitle('Merit badges covered (if any)');
  form.addParagraphTextItem().setTitle('Description');
  form.addTextItem().setTitle('Your email (only if we have questions; never published)');

  const ss = SpreadsheetApp.create('Scout Event Finder - Event submissions');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  SpreadsheetApp.flush();
  Utilities.sleep(3000);

  const resp = ss.getSheets().filter(s => s.getName().indexOf('Form Responses') === 0)[0];
  // Timestamp + 14 questions = columns A..O; the email is O. Approval goes in P.
  resp.getRange('P1').setValue('Approved (type yes)').setFontWeight('bold').setBackground('#fff2cc');
  resp.setFrozenRows(1);

  const appr = ss.insertSheet('Approved');
  appr.getRange('A1').setFormula(
    "=QUERY('" + resp.getName() + "'!A:P, \"select A,B,C,D,E,F,G,H,I,J,K,L,M,N where lower(P) = 'yes'\", 1)");
  appr.getRange('A1:N1').setFontWeight('bold');

  const blank = ss.getSheetByName('Sheet1');
  if (blank && ss.getSheets().length > 1) ss.deleteSheet(blank);

  Logger.log('Form to share:   ' + form.getPublishedUrl());
  Logger.log('Edit the form:   ' + form.getEditUrl());
  Logger.log('Responses Sheet: ' + ss.getUrl());
  Logger.log('Next: in the Sheet, File > Share > Publish to web > choose the "Approved" tab and ' +
             '"Comma-separated values (.csv)" > Publish, and send that link.');
}
