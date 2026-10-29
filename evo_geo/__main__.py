import json
from .core import Engine, StepInputs, state_to_dict

def main():
    engine=Engine()
    for _ in range(10):
        engine.step(StepInputs({i:(0,0) for i in engine.state.vertices},[]))
    print(json.dumps({"spec_version":engine.contract.spec_version,"step":engine.state.step,"vertices":len(engine.state.vertices),"edges":len(engine.state.edges),"events":len(engine.archive.events),"archive_valid":engine.archive.verify(),"state":state_to_dict(engine.state)},sort_keys=True,indent=2))

if __name__=="__main__": main()
