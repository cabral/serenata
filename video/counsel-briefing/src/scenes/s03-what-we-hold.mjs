import { a, esc, icon, num, tag } from '../components.mjs';

export default (c) => {
  const cards = [
    {
      glyph: 'person',
      big: c.f('absent'),
      text: `of ${c.f('orgRows')} organisation records do not say whether the organisation is a person.`,
    },
    {
      glyph: 'mail',
      big: c.f('addressShaped'),
      text: `address-shaped values in 7 retained columns. ${c.f('personShaped')} look like a person's own.`,
    },
    {
      glyph: 'idcard',
      big: 'SE',
      text: `In Sweden a sole trader's registration number is their ${c.f('personnummer')}.`,
    },
    {
      glyph: 'doc',
      big: 'TED',
      text: 'The source notice stays public. Our opaque key links back to it.',
    },
  ];
  const pos = [
    [96, 150],
    [976, 150],
    [96, 500],
    [976, 500],
  ];
  const card = (k) =>
    `<div class="hc" style="left:${pos[k][0]}px;top:${pos[k][1]}px" ${a('wipeX', { at: 0.1, dur: 0.55 })}>` +
    `<div class="hci">${icon(cards[k].glyph, { px: 120, color: '#000', accent: 'var(--purple)' })}</div>` +
    `<div class="hcb pix">${esc(cards[k].big)}</div>` +
    `<div class="hct">${esc(cards[k].text)}</div></div>`;

  return {
    id: 's03-what-we-hold',
    chapterId: 'hold',
    chapter: 'What we hold',
    title: 'What we hold',
    css: `
      .s03 .hc { position: absolute; width: 848px; height: 330px; background: var(--soft); color: #000; padding: 30px 38px; }
      .s03 .hci { position: absolute; right: 34px; top: 28px; }
      .s03 .hcb { font-size: 118px; color: var(--purple); }
      .s03 .hct { font-size: 37px; line-height: 1.25; margin-top: 12px; max-width: 700px; }
      .s03 .big { position: absolute; top: 200px; }
      .s03 .big .num { font-size: 250px; }
      .s03 .statement { position: absolute; left: 96px; top: 200px; width: 1650px; font-size: 118px; }
    `,
    beats: [
      {
        say: `Contact details appear in ${c.f('contactDetails')} of the notices we measured. We drop them by element path, along with beneficial owners and named evaluators: ${c.f('leafDrop')} of all leaf elements.`,
        show: () =>
          `<div class="s03">` +
          `<div class="big" style="left:96px">${num(c.f('contactDetails'), { at: 0.2 })}` +
          `<div style="margin-top:22px;font-size:40px;max-width:760px" ${a('fade', { at: 1.3 })}>of measured notices carry contact details.</div></div>` +
          `<div class="big" style="left:1000px">${num(c.f('leafDrop'), { at: 0.6 })}` +
          `<div style="margin-top:22px;font-size:40px;max-width:760px" ${a('fade', { at: 1.6 })}>of all leaf elements dropped by path before a record exists.</div></div>` +
          `<div class="abs" style="left:96px;top:700px;display:flex;gap:16px">${tag('Contact blocks', { kind: 'k', at: 2.2 })}${tag('Beneficial owners', { kind: 'k', at: 2.5 })}${tag('Named evaluators', { kind: 'k', at: 2.8 })}</div>` +
          `</div>`,
      },
      {
        say: `That is structural suppression. It removes specified paths, which is less than anonymising the data.`,
        show: () =>
          `<div class="s03"><div class="statement pix" ${a('wipeX', { at: 0.1, dur: 0.7 })}>Structural suppression is <span class="lilac">not anonymisation.</span></div>` +
          `<div class="abs" style="left:100px;top:640px;font-size:40px;max-width:1300px;color:var(--soft)" ${a('fade', { at: 1.2 })}>It removes specified paths. It does not remove everything that could identify someone.</div></div>`,
      },
      {
        say: `For ${c.f('absent')} of the ${c.f('orgRows')} organisation records, the notice doesn't say whether the organisation is a company or a person trading in their own name. Not provided means unknown here.`,
        stay: true,
        show: () => `<div class="s03">${card(0)}</div>`,
      },
      {
        say: `Publishers also type contact addresses into fields that aren't contact fields: ${c.f('addressShaped')} across seven retained columns, ${c.f('personShaped')} shaped like a person's own. We only searched for email-shaped strings, so the true number is larger.`,
        stay: true,
        show: () => `<div class="s03">${card(1)}</div>`,
      },
      {
        say: `In Sweden, a sole trader's registration number is their personnummer.`,
        stay: true,
        show: () => `<div class="s03">${card(2)}</div>`,
      },
      {
        say: `And every notice stays public, so our opaque keys lead back to it.`,
        stay: true,
        show: () => `<div class="s03">${card(3)}</div>`,
      },
    ],
  };
};
