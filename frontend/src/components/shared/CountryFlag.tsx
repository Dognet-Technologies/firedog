import React from 'react';

interface CountryFlagProps {
  countryCode: string;
  showName?: boolean;
}

const countryNames: Record<string, string> = {
  US: 'United States',
  CN: 'China',
  RU: 'Russia',
  BR: 'Brazil',
  DE: 'Germany',
  FR: 'France',
  GB: 'United Kingdom',
  IN: 'India',
  JP: 'Japan',
  KR: 'South Korea',
  NL: 'Netherlands',
  CA: 'Canada',
  AU: 'Australia',
  IT: 'Italy',
  ES: 'Spain',
  UA: 'Ukraine',
  IR: 'Iran',
  TR: 'Turkey',
  PL: 'Poland',
  SG: 'Singapore',
  HK: 'Hong Kong',
  TW: 'Taiwan',
  MX: 'Mexico',
  AR: 'Argentina',
  ZA: 'South Africa',
};

const getEmojiFlag = (countryCode: string): string => {
  if (!countryCode || countryCode.length !== 2) return '🌐';
  const code = countryCode.toUpperCase();
  // Unicode regional indicator symbols: A=0x1F1E6, offset by char code
  const codePointA = code.charCodeAt(0) - 65 + 0x1f1e6;
  const codePointB = code.charCodeAt(1) - 65 + 0x1f1e6;
  return String.fromCodePoint(codePointA, codePointB);
};

const CountryFlag: React.FC<CountryFlagProps> = ({ countryCode, showName }) => {
  const code = countryCode?.toUpperCase() || '';
  const flag = getEmojiFlag(code);
  const name = countryNames[code] || code || 'Unknown';

  return (
    <span className="country-flag" title={name}>
      <span className="country-flag-emoji">{flag}</span>
      {showName && <span className="country-flag-name">{name}</span>}
    </span>
  );
};

export default CountryFlag;
