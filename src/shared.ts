const SIZES = [8, 10, 12, 14, 18, 24] as const;

export const families = [
  ...SIZES.map((pt) => `R95 Sans Serif ${pt}pt`),
  ...SIZES.map((pt) => `R95 Sans Serif HiRes ${pt}pt`),
  ...SIZES.map((pt) => `R95 Serif ${pt}pt`),
  ...SIZES.map((pt) => `R95 Serif HiRes ${pt}pt`),
];

export const basic =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!"#$%&\'()*+,-./:;<=>?@[]^_`{|}~'.split(
    '',
  );

export const supplement =
  ' ¡¢£¤¥¦§¨©ª«¬®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ'.split(
    '',
  );
