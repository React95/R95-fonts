import {
  Frame,
  Modal,
  Fieldset,
  Dropdown,
  Input,
  Checkbox,
  TitleBar,
} from '@react95/core';
import { ComponentProps, ReactNode, useContext, useState } from 'react';
import { families } from './shared';
import { ModalContext } from './ModalContext';

export type RenderContentProps = {
  italic: boolean;
  bold: boolean;
  fontFamily: string;
  fontSize: number;
};

const ChangeFontModal = ({
  renderContent,
  title,
  fontSize: size = 54,
  bold: weight = false,
  italic: style = false,
  position: defaultPosition,
  icon,
}: {
  renderContent: (props: RenderContentProps) => ReactNode;
  title: string;
  position: NonNullable<
    ComponentProps<typeof Modal>['dragOptions']
  >['defaultPosition'];
  icon: ComponentProps<typeof Modal>['icon'];
} & Partial<Omit<RenderContentProps, 'fontFamily'>>) => {
  const [fontSize, setFontSize] = useState(size);
  const [bold, setBold] = useState(weight);
  const [italic, setItalic] = useState(style);
  const [fontFamily, setFontFamily] = useState<string>(families[0]);
  const { modal, removeModal } = useContext(ModalContext);

  return (
    modal.includes(title) && (
      <Modal
        className="default"
        titleBarOptions={[
          <TitleBar.Close
            key="close"
            onClick={() => {
              removeModal(title);
            }}
          />,
        ]}
        title={title}
        dragOptions={{
          defaultPosition,
        }}
        icon={icon}
      >
        <Fieldset legend="Config">
          <Frame display="flex" gap="$8" alignItems="center">
            <Dropdown
              onChange={({ target }) => {
                setFontFamily((target as HTMLSelectElement).value);
              }}
              defaultValue={fontFamily}
              options={families}
            />

            <Input
              type="number"
              onChange={({ target }: { target: HTMLInputElement }) => {
                setFontSize(parseInt(target.value));
              }}
              defaultValue={fontSize}
              height="26px"
            />
            <Checkbox checked={italic} onChange={() => setItalic(!italic)}>
              Italic
            </Checkbox>
            <Checkbox checked={bold} onChange={() => setBold(!bold)}>
              Bold
            </Checkbox>
          </Frame>
        </Fieldset>

        {renderContent({ italic, bold, fontFamily, fontSize })}
      </Modal>
    )
  );
};

export default ChangeFontModal;
