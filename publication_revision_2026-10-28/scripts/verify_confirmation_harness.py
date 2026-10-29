"""Known-good and known-bad programs validate the three execution paths."""
import json
from pathlib import Path
from confirmation_functional import execute,init
ROOT=Path(__file__).resolve().parents[1]
init(json.loads((ROOT/'records/tool_paths.json').read_text())['jdk'])
programs={
 'python':('n=int(input());print(n*2)','n=int(input());print(n+1)','raise SystemExit(0)'),
 'cpp':('#include <iostream>\nint main(){int n;std::cin>>n;std::cout<<n*2;}',
        '#include <iostream>\nint main(){int n;std::cin>>n;std::cout<<n+1;}','int main(){return 0;}'),
 'java':('import java.util.*; public class Main{public static void main(String[] x){int n=new Scanner(System.in).nextInt();System.out.println(n*2);}}',
         'import java.util.*; public class Main{public static void main(String[] x){int n=new Scanner(System.in).nextInt();System.out.println(n+1);}}',
         'public class Main{public static void main(String[] x){System.exit(0);}}')}
results=[]
for lang,codes in programs.items():
    task={'language':lang,'tests':[{'kind':'sentinel','index':0,'input':'3\n','output':'6\n'},{'kind':'sentinel','index':1,'input':'-7\n','output':'-14\n'}]}
    for label,code,expected in zip(('correct','incorrect','early_exit'),codes,(True,False,False)):
        r=execute(task,code);assert r['compile_ok'],(lang,label,r)
        assert bool(r['benchmark_pass'])==expected,(lang,label,r)
        results.append(dict(language=lang,case=label,expected=expected,result=r))
(ROOT/'records/harness_controls.json').write_text(json.dumps(results,indent=2))
print('HARNESS_CONTROLS_PASSED',len(results),flush=True)
